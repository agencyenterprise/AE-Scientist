import os

working_dir = os.path.join(os.getcwd(), "working")
os.makedirs(working_dir, exist_ok=True)

import json
import math
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from datasets import load_dataset
from sklearn.metrics import accuracy_score
from sklearn.metrics import auc as sk_auc
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_auc_score, roc_curve
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import resnet18

# =====================
# Multiprocessing / pickling bugfix
# =====================
try:
    import torch.multiprocessing as mp

    if mp.get_start_method(allow_none=True) is None:
        mp.set_start_method("fork", force=True)
    else:
        if mp.get_start_method() == "spawn":
            mp.set_start_method("fork", force=True)
except Exception:
    pass

# =====================
# GPU/CPU handling (MANDATORY)
# =====================
torch.cuda.set_device(0)
device = torch.device("cuda:0")
print(f"Using device: {device}")

# =====================
# Reproducibility
# =====================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
torch.backends.cudnn.deterministic = False
torch.backends.cudnn.benchmark = True


# =====================
# Experiment config
# =====================
@dataclass
class Config:
    img_size: int = 224
    batch_size: int = 128
    num_workers: int = 8
    num_epochs: int = 12
    lr: float = 3e-4
    weight_decay: float = 1e-4
    patience: int = 3
    min_delta: float = 1e-4
    train_frac: float = 0.70
    val_frac: float = 0.15
    test_frac: float = 0.15
    group_bucket_size: int = 50
    max_train_samples: Optional[int] = 30000
    max_val_samples: Optional[int] = 8000
    max_test_samples: Optional[int] = 8000
    bootstrap_iters: int = 500


cfg = Config()

# =====================
# Data containers (MANDATORY naming convention)
# =====================
experiment_data = {
    "pcam_or_fallback": {
        "metrics": {"train": [], "val": [], "test": []},
        "losses": {"train": [], "val": []},
        "predictions": [],
        "ground_truth": [],
        "groups": [],
        "meta": {},
    }
}


# =====================
# Utilities
# =====================
def timestamp() -> float:
    return time.time()


def to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy / torch objects to JSON-serializable Python types."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if torch.is_tensor(obj):
        return obj.detach().cpu().tolist()
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    # Fallback: stringify unknown objects
    return str(obj)


def try_load_pcam() -> Tuple[str, Dict[str, object]]:
    """Try multiple HF dataset IDs for PCam; return (name, dataset_dict)."""
    candidates = [
        ("pcam", None),
        ("timm/pcam", None),
        ("1aurent/pcam", None),
        ("medmnist", "pathmnist"),
    ]
    last_err = None
    for ds_id, config_name in candidates:
        try:
            if config_name is None:
                ds = load_dataset(ds_id)
            else:
                ds = load_dataset(ds_id, config_name)
            if "train" not in ds:
                continue
            return f"{ds_id}{'' if config_name is None else '/' + config_name}", ds
        except Exception as e:
            last_err = repr(e)
            continue
    print("[WARN] Could not load PCam-like dataset from HF candidates. Falling back to CIFAR-10.")
    if last_err is not None:
        print("[WARN] Last dataset load error:", last_err)
    ds = load_dataset("uoft-cs/cifar10")
    return "uoft-cs/cifar10", ds


def infer_image_label_columns(split) -> Tuple[str, str]:
    cols = split.column_names
    img_col = None
    label_col = None
    for c in ["image", "img", "pixel_values"]:
        if c in cols:
            img_col = c
            break
    for c in ["label", "labels", "target", "y"]:
        if c in cols:
            label_col = c
            break
    if img_col is None:
        for c in cols:
            if str(split.features[c]).lower().find("image") >= 0:
                img_col = c
                break
    if label_col is None:
        for c in cols:
            f = split.features[c]
            if getattr(f, "num_classes", None) is not None:
                label_col = c
                break
    if img_col is None or label_col is None:
        raise ValueError(f"Could not infer image/label columns. columns={cols}")
    return img_col, label_col


def to_binary_label(label: int, dataset_name: str) -> int:
    if "cifar10" in dataset_name:
        return int(label in [5, 6, 7, 8, 9])
    if "medmnist/pathmnist" in dataset_name:
        return int(label in [7, 8])
    return int(label)


def build_groups(num_examples: int, bucket_size: int) -> np.ndarray:
    return (np.arange(num_examples) // bucket_size).astype(np.int64)


def stratified_group_split(
    groups: np.ndarray,
    labels: np.ndarray,
    train_frac: float,
    val_frac: float,
    test_frac: float,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-6
    rng = np.random.default_rng(seed)
    unique_groups = np.unique(groups)

    g2label: Dict[int, int] = {}
    for g in unique_groups:
        idxs = np.where(groups == g)[0]
        maj = int(np.round(labels[idxs].mean()))
        g2label[int(g)] = maj

    g0 = [g for g in unique_groups.tolist() if g2label[int(g)] == 0]
    g1 = [g for g in unique_groups.tolist() if g2label[int(g)] == 1]
    rng.shuffle(g0)
    rng.shuffle(g1)

    def split_list(glst: List[int]) -> Tuple[List[int], List[int], List[int]]:
        n = len(glst)
        n_train = int(round(n * train_frac))
        n_val = int(round(n * val_frac))
        n_test = n - n_train - n_val
        train_g = glst[:n_train]
        val_g = glst[n_train : n_train + n_val]
        test_g = glst[n_train + n_val :]
        assert len(test_g) == n_test
        return train_g, val_g, test_g

    tr0, va0, te0 = split_list(g0)
    tr1, va1, te1 = split_list(g1)

    train_groups = np.array(tr0 + tr1, dtype=np.int64)
    val_groups = np.array(va0 + va1, dtype=np.int64)
    test_groups = np.array(te0 + te1, dtype=np.int64)

    rng.shuffle(train_groups)
    rng.shuffle(val_groups)
    rng.shuffle(test_groups)

    train_idx = np.where(np.isin(groups, train_groups))[0]
    val_idx = np.where(np.isin(groups, val_groups))[0]
    test_idx = np.where(np.isin(groups, test_groups))[0]

    assert len(set(groups[train_idx]).intersection(set(groups[val_idx]))) == 0
    assert len(set(groups[train_idx]).intersection(set(groups[test_idx]))) == 0
    assert len(set(groups[val_idx]).intersection(set(groups[test_idx]))) == 0

    return {"train": train_idx, "val": val_idx, "test": test_idx}


def aggregate_by_group(
    probs: np.ndarray, labels: np.ndarray, groups: np.ndarray, agg: str = "mean"
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    unique_groups = np.unique(groups)
    g_probs = []
    g_labels = []
    for g in unique_groups:
        idxs = np.where(groups == g)[0]
        if agg == "mean":
            p = float(np.mean(probs[idxs]))
        elif agg == "max":
            p = float(np.max(probs[idxs]))
        else:
            raise ValueError("Unknown agg")
        y = int(np.round(labels[idxs].mean()))
        g_probs.append(p)
        g_labels.append(y)
    return unique_groups, np.asarray(g_probs), np.asarray(g_labels)


def safe_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, y_score))


def bootstrap_auc_ci(
    y_true: np.ndarray, y_score: np.ndarray, iters: int, seed: int = 42
) -> Tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    aucs = []
    for _ in range(iters):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        ys = y_score[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, ys))
    if len(aucs) == 0:
        return float("nan"), float("nan"), float("nan")
    aucs = np.asarray(aucs)
    return float(np.mean(aucs)), float(np.quantile(aucs, 0.025)), float(np.quantile(aucs, 0.975))


class HFImageBinaryDataset(Dataset):
    def __init__(
        self,
        hf_split,
        indices: np.ndarray,
        img_col: str,
        label_col: str,
        dataset_name: str,
        transform=None,
        group_ids: Optional[np.ndarray] = None,
    ):
        self.hf_split = hf_split
        self.indices = indices.astype(np.int64)
        self.img_col = img_col
        self.label_col = label_col
        self.dataset_name = dataset_name
        self.transform = transform
        self.group_ids = group_ids

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i: int):
        idx = int(self.indices[i])
        ex = self.hf_split[idx]
        img = ex[self.img_col]
        if hasattr(img, "convert"):
            img = img.convert("RGB")
        label_raw = ex[self.label_col]
        if isinstance(label_raw, (list, tuple, np.ndarray)):
            label_raw = int(label_raw[0]) if len(label_raw) else 0
        y = to_binary_label(int(label_raw), self.dataset_name)
        if self.transform is not None:
            x = self.transform(img)
        else:
            x = transforms.ToTensor()(img)
        g = -1
        if self.group_ids is not None:
            g = int(self.group_ids[idx])
        return {
            "pixel_values": x,
            "labels": torch.tensor(y, dtype=torch.long),
            "group": torch.tensor(g, dtype=torch.long),
        }


class SmallCNN(nn.Module):
    def __init__(self, num_classes: int = 2):
        super().__init__()

        def block(in_ch, out_ch):
            return nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            )

        self.net = nn.Sequential(
            block(3, 32),
            block(32, 64),
            block(64, 128),
            block(128, 256),
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        x = self.net(x)
        x = self.head(x)
        return x


def make_transforms(img_size: int):
    imagenet_mean = [0.485, 0.456, 0.406]
    imagenet_std = [0.229, 0.224, 0.225]
    train_tf = transforms.Compose(
        [
            transforms.Resize(int(img_size * 1.15)),
            transforms.RandomResizedCrop(img_size, scale=(0.85, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(brightness=0.08, contrast=0.08, saturation=0.05, hue=0.02),
            transforms.ToTensor(),
            transforms.Normalize(mean=imagenet_mean, std=imagenet_std),
        ]
    )
    eval_tf = transforms.Compose(
        [
            transforms.Resize(int(img_size * 1.15)),
            transforms.CenterCrop(img_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=imagenet_mean, std=imagenet_std),
        ]
    )
    return train_tf, eval_tf


def compute_class_weights(labels: np.ndarray) -> torch.Tensor:
    counts = np.bincount(labels.astype(int), minlength=2).astype(np.float64)
    counts[counts == 0] = 1.0
    w = counts.sum() / (2.0 * counts)
    return torch.tensor(w, dtype=torch.float32)


def run_one_epoch(
    model, loader, optimizer, criterion, is_train: bool
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    if is_train:
        model.train()
    else:
        model.eval()

    losses = []
    all_probs = []
    all_y = []
    all_g = []

    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items() if isinstance(v, torch.Tensor)}
        x = batch["pixel_values"]
        y = batch["labels"]
        g = batch["group"]

        with torch.set_grad_enabled(is_train):
            logits = model(x)
            loss = criterion(logits, y)
            if is_train:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        probs = torch.softmax(logits, dim=1)[:, 1].detach().float().cpu().numpy()
        losses.append(float(loss.detach().cpu().item()))
        all_probs.append(probs)
        all_y.append(y.detach().cpu().numpy())
        all_g.append(g.detach().cpu().numpy())

    mean_loss = float(np.mean(losses)) if len(losses) else float("nan")
    all_probs = np.concatenate(all_probs) if len(all_probs) else np.array([])
    all_y = np.concatenate(all_y) if len(all_y) else np.array([])
    all_g = np.concatenate(all_g) if len(all_g) else np.array([])
    return mean_loss, all_probs, all_y, all_g


def train_model_baseline(
    model_name: str,
    model: nn.Module,
    train_loader,
    val_loader,
    class_weights: torch.Tensor,
    num_epochs: int,
    lr: float,
    weight_decay: float,
    patience: int,
    min_delta: float,
    dataset_key: str,
) -> Dict[str, object]:

    model = model.to(device)
    class_weights = class_weights.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    best_val_auc = -1e9
    best_state = None
    best_epoch = -1
    bad_epochs = 0

    hist = {
        "model_name": model_name,
        "train_loss": [],
        "val_loss": [],
        "train_group_auc": [],
        "val_group_auc": [],
        "epoch_time_s": [],
    }

    for epoch in range(1, num_epochs + 1):
        t0 = timestamp()
        train_loss, tr_probs, tr_y, tr_g = run_one_epoch(
            model, train_loader, optimizer, criterion, is_train=True
        )
        val_loss, va_probs, va_y, va_g = run_one_epoch(
            model, val_loader, optimizer, criterion, is_train=False
        )

        _, tr_g_probs, tr_g_y = aggregate_by_group(tr_probs, tr_y, tr_g, agg="mean")
        _, va_g_probs, va_g_y = aggregate_by_group(va_probs, va_y, va_g, agg="mean")
        tr_auc = safe_roc_auc(tr_g_y, tr_g_probs)
        va_auc = safe_roc_auc(va_g_y, va_g_probs)

        t1 = timestamp()

        hist["train_loss"].append(train_loss)
        hist["val_loss"].append(val_loss)
        hist["train_group_auc"].append(tr_auc)
        hist["val_group_auc"].append(va_auc)
        hist["epoch_time_s"].append(t1 - t0)

        experiment_data[dataset_key]["losses"]["train"].append(
            {"epoch": epoch, "ts": t1, "loss": train_loss, "model": model_name}
        )
        experiment_data[dataset_key]["losses"]["val"].append(
            {"epoch": epoch, "ts": t1, "loss": val_loss, "model": model_name}
        )
        experiment_data[dataset_key]["metrics"]["train"].append(
            {"epoch": epoch, "ts": t1, "group_roc_auc": tr_auc, "model": model_name}
        )
        experiment_data[dataset_key]["metrics"]["val"].append(
            {"epoch": epoch, "ts": t1, "group_roc_auc": va_auc, "model": model_name}
        )

        # MANDATORY print validation loss each epoch
        print(f"Epoch {epoch}: validation_loss = {val_loss:.4f}")
        print(
            f"  [{model_name}] train_loss={train_loss:.4f} val_loss={val_loss:.4f} train_group_auc={tr_auc:.4f} val_group_auc={va_auc:.4f}"
        )

        improved = (va_auc > best_val_auc + min_delta) or (
            math.isnan(best_val_auc) and not math.isnan(va_auc)
        )
        if improved:
            best_val_auc = va_auc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                print(
                    f"  Early stopping at epoch {epoch} (best_epoch={best_epoch}, best_val_group_auc={best_val_auc:.4f})"
                )
                break

    if best_state is not None:
        model.load_state_dict(best_state, strict=True)
    model = model.to(device)

    return {"model": model, "history": hist, "best_epoch": best_epoch, "best_val_auc": best_val_auc}


def evaluate_and_save(
    model_name: str,
    model: nn.Module,
    test_loader,
    dataset_key: str,
    out_prefix: str,
    bootstrap_iters: int = 500,
) -> Dict[str, object]:
    model.eval().to(device)
    criterion = nn.CrossEntropyLoss()

    test_loss, te_probs, te_y, te_g = run_one_epoch(
        model, test_loader, optimizer=None, criterion=criterion, is_train=False
    )

    g_ids, g_probs, g_y = aggregate_by_group(te_probs, te_y, te_g, agg="mean")
    group_auc = safe_roc_auc(g_y, g_probs)

    group_pred = (g_probs >= 0.5).astype(int)
    acc = float(accuracy_score(g_y, group_pred)) if len(g_y) else float("nan")
    cm = (
        confusion_matrix(g_y, group_pred, labels=[0, 1])
        if len(g_y)
        else np.zeros((2, 2), dtype=int)
    )

    if len(np.unique(g_y)) >= 2:
        prec, rec, _ = precision_recall_curve(g_y, g_probs)
        pr_auc = float(sk_auc(rec, prec))
    else:
        prec, rec = np.array([1.0]), np.array([0.0])
        pr_auc = float("nan")

    mean_auc, lo_auc, hi_auc = bootstrap_auc_ci(g_y, g_probs, iters=bootstrap_iters, seed=SEED)

    np.save(os.path.join(working_dir, f"{out_prefix}_patch_probs.npy"), te_probs)
    np.save(os.path.join(working_dir, f"{out_prefix}_patch_y.npy"), te_y)
    np.save(os.path.join(working_dir, f"{out_prefix}_patch_groups.npy"), te_g)
    np.save(os.path.join(working_dir, f"{out_prefix}_group_ids.npy"), g_ids)
    np.save(os.path.join(working_dir, f"{out_prefix}_group_probs.npy"), g_probs)
    np.save(os.path.join(working_dir, f"{out_prefix}_group_y.npy"), g_y)
    np.save(os.path.join(working_dir, f"{out_prefix}_confusion_matrix.npy"), cm)

    if len(np.unique(g_y)) >= 2:
        fpr, tpr, _ = roc_curve(g_y, g_probs)
        plt.figure(figsize=(6, 5))
        plt.plot(fpr, tpr, label=f"{model_name} (AUC={group_auc:.3f})")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"Group-level ROC ({model_name})")
        plt.legend(loc="lower right")
        fig_path = os.path.join(working_dir, f"roc_group_{out_prefix}.png")
        plt.tight_layout()
        plt.savefig(fig_path, dpi=160)
        plt.close()
        np.save(os.path.join(working_dir, f"{out_prefix}_roc_fpr.npy"), fpr)
        np.save(os.path.join(working_dir, f"{out_prefix}_roc_tpr.npy"), tpr)

    plt.figure(figsize=(6, 5))
    plt.plot(rec, prec, label=f"{model_name} (PR-AUC={pr_auc:.3f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title(f"Group-level PR ({model_name})")
    plt.legend(loc="lower left")
    fig_path = os.path.join(working_dir, f"pr_group_{out_prefix}.png")
    plt.tight_layout()
    plt.savefig(fig_path, dpi=160)
    plt.close()
    np.save(os.path.join(working_dir, f"{out_prefix}_pr_recall.npy"), rec)
    np.save(os.path.join(working_dir, f"{out_prefix}_pr_precision.npy"), prec)

    experiment_data[dataset_key]["metrics"]["test"].append(
        {
            "ts": timestamp(),
            "model": model_name,
            "test_loss": float(test_loss),
            "group_roc_auc": float(group_auc),
            "group_pr_auc": float(pr_auc),
            "group_accuracy": float(acc),
            "bootstrap_mean_auc": float(mean_auc),
            "bootstrap_ci_low": float(lo_auc),
            "bootstrap_ci_high": float(hi_auc),
        }
    )

    print(
        f"[TEST] {model_name}: loss={test_loss:.4f} group_auc={group_auc:.4f} "
        f"acc={acc:.4f} pr_auc={pr_auc:.4f}  AUC_CI95=[{lo_auc:.4f}, {hi_auc:.4f}] (mean_boot={mean_auc:.4f})"
    )

    return {
        "test_loss": float(test_loss),
        "group_auc": float(group_auc),
        "acc": float(acc),
        "pr_auc": float(pr_auc),
        "cm": cm,
        "auc_ci": (float(lo_auc), float(hi_auc)),
        "bootstrap_mean_auc": float(mean_auc),
    }


def make_dataloader_safe(
    ds_obj: Dataset, batch_size: int, shuffle: bool, num_workers: int, pin_memory: bool
):
    """Create DataLoader; if worker startup/pickling fails, fallback to num_workers=0."""
    try:
        loader = DataLoader(
            ds_obj,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=pin_memory,
        )
        _ = next(iter(loader))
        return loader
    except Exception as e:
        print("[WARN] DataLoader multiprocessing failed; falling back to num_workers=0")
        print("[WARN] Error:", repr(e))
        loader = DataLoader(
            ds_obj,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=0,
            pin_memory=pin_memory,
        )
        return loader


# =====================
# Load dataset
# =====================
dataset_name, ds = try_load_pcam()
print("Loaded dataset:", dataset_name)

source_train = ds["train"]
img_col, label_col = infer_image_label_columns(source_train)
print("Inferred columns:", img_col, label_col)

N_total = len(source_train)
if cfg.max_train_samples is not None:
    cap_target = (
        (cfg.max_train_samples or 0) + (cfg.max_val_samples or 0) + (cfg.max_test_samples or 0)
    )
    N_cap = min(N_total, cap_target)
else:
    N_cap = N_total

labels_all = []
for i in range(N_cap):
    ex = source_train[int(i)]
    lr0 = ex[label_col]
    if isinstance(lr0, (list, tuple, np.ndarray)):
        lr0 = int(lr0[0]) if len(lr0) else 0
    labels_all.append(to_binary_label(int(lr0), dataset_name))
labels_all = np.asarray(labels_all, dtype=np.int64)

groups_all = build_groups(N_cap, cfg.group_bucket_size)

splits = stratified_group_split(
    groups_all, labels_all, cfg.train_frac, cfg.val_frac, cfg.test_frac, seed=SEED
)
train_idx = splits["train"]
val_idx = splits["val"]
test_idx = splits["test"]

if cfg.max_train_samples is not None and len(train_idx) > cfg.max_train_samples:
    train_idx = train_idx[: cfg.max_train_samples]
if cfg.max_val_samples is not None and len(val_idx) > cfg.max_val_samples:
    val_idx = val_idx[: cfg.max_val_samples]
if cfg.max_test_samples is not None and len(test_idx) > cfg.max_test_samples:
    test_idx = test_idx[: cfg.max_test_samples]

assert len(set(groups_all[train_idx]).intersection(set(groups_all[val_idx]))) == 0
assert len(set(groups_all[train_idx]).intersection(set(groups_all[test_idx]))) == 0
assert len(set(groups_all[val_idx]).intersection(set(groups_all[test_idx]))) == 0

train_counts = np.bincount(labels_all[train_idx], minlength=2)
val_counts = np.bincount(labels_all[val_idx], minlength=2)
test_counts = np.bincount(labels_all[test_idx], minlength=2)
print("Class counts (0/1):")
print("  train:", train_counts.tolist())
print("  val  :", val_counts.tolist())
print("  test :", test_counts.tolist())

experiment_data["pcam_or_fallback"]["meta"] = {
    "dataset_name": dataset_name,
    "img_col": img_col,
    "label_col": label_col,
    "N_cap": int(N_cap),
    "split_sizes": {
        "train": int(len(train_idx)),
        "val": int(len(val_idx)),
        "test": int(len(test_idx)),
    },
    "class_counts": {
        "train": train_counts.tolist(),
        "val": val_counts.tolist(),
        "test": test_counts.tolist(),
    },
    "cfg": cfg.__dict__,
}

# =====================
# Dataloaders
# =====================
train_tf, eval_tf = make_transforms(cfg.img_size)

train_ds = HFImageBinaryDataset(
    source_train,
    train_idx,
    img_col,
    label_col,
    dataset_name,
    transform=train_tf,
    group_ids=groups_all,
)
val_ds = HFImageBinaryDataset(
    source_train, val_idx, img_col, label_col, dataset_name, transform=eval_tf, group_ids=groups_all
)
test_ds = HFImageBinaryDataset(
    source_train,
    test_idx,
    img_col,
    label_col,
    dataset_name,
    transform=eval_tf,
    group_ids=groups_all,
)

pin_memory = device.type == "cuda"
train_loader = make_dataloader_safe(
    train_ds, cfg.batch_size, shuffle=True, num_workers=cfg.num_workers, pin_memory=pin_memory
)
val_loader = make_dataloader_safe(
    val_ds, cfg.batch_size, shuffle=False, num_workers=cfg.num_workers, pin_memory=pin_memory
)
test_loader = make_dataloader_safe(
    test_ds, cfg.batch_size, shuffle=False, num_workers=cfg.num_workers, pin_memory=pin_memory
)

cw = compute_class_weights(labels_all[train_idx])
print("Class weights:", cw.tolist())

# =====================
# Train baseline A: SmallCNN
# =====================
small_cnn = SmallCNN(num_classes=2)
res_a = train_model_baseline(
    model_name="smallcnn_scratch",
    model=small_cnn,
    train_loader=train_loader,
    val_loader=val_loader,
    class_weights=cw,
    num_epochs=cfg.num_epochs,
    lr=cfg.lr,
    weight_decay=cfg.weight_decay,
    patience=cfg.patience,
    min_delta=cfg.min_delta,
    dataset_key="pcam_or_fallback",
)

# =====================
# Train baseline B: ResNet-18 transfer
# =====================
try:
    resnet = resnet18(weights="IMAGENET1K_V1")
except Exception:
    resnet = resnet18(pretrained=True)
resnet.fc = nn.Linear(resnet.fc.in_features, 2)
res_b = train_model_baseline(
    model_name="resnet18_finetune",
    model=resnet,
    train_loader=train_loader,
    val_loader=val_loader,
    class_weights=cw,
    num_epochs=cfg.num_epochs,
    lr=cfg.lr,
    weight_decay=cfg.weight_decay,
    patience=cfg.patience,
    min_delta=cfg.min_delta,
    dataset_key="pcam_or_fallback",
)

# =====================
# Evaluate both on test
# =====================
ev_a = evaluate_and_save(
    "smallcnn_scratch",
    res_a["model"],
    test_loader,
    "pcam_or_fallback",
    out_prefix="pcam_smallcnn",
    bootstrap_iters=cfg.bootstrap_iters,
)
cev_a = ev_a

_ev_b = evaluate_and_save(
    "resnet18_finetune",
    res_b["model"],
    test_loader,
    "pcam_or_fallback",
    out_prefix="pcam_resnet18",
    bootstrap_iters=cfg.bootstrap_iters,
)
cev_b = _ev_b

if (not math.isnan(cev_b["group_auc"])) and (
    math.isnan(cev_a["group_auc"]) or cev_b["group_auc"] >= cev_a["group_auc"]
):
    experiment_data["pcam_or_fallback"]["predictions"] = np.load(
        os.path.join(working_dir, "pcam_resnet18_group_probs.npy")
    ).tolist()
    experiment_data["pcam_or_fallback"]["ground_truth"] = np.load(
        os.path.join(working_dir, "pcam_resnet18_group_y.npy")
    ).tolist()
    experiment_data["pcam_or_fallback"]["groups"] = np.load(
        os.path.join(working_dir, "pcam_resnet18_group_ids.npy")
    ).tolist()
else:
    experiment_data["pcam_or_fallback"]["predictions"] = np.load(
        os.path.join(working_dir, "pcam_smallcnn_group_probs.npy")
    ).tolist()
    experiment_data["pcam_or_fallback"]["ground_truth"] = np.load(
        os.path.join(working_dir, "pcam_smallcnn_group_y.npy")
    ).tolist()
    experiment_data["pcam_or_fallback"]["groups"] = np.load(
        os.path.join(working_dir, "pcam_smallcnn_group_ids.npy")
    ).tolist()


# =====================
# Visualizations: learning curves
# =====================
def plot_learning_curves(hist_a: Dict[str, object], hist_b: Dict[str, object], out_name: str):
    epochs_a = np.arange(1, len(hist_a["train_loss"]) + 1)
    epochs_b = np.arange(1, len(hist_b["train_loss"]) + 1)

    plt.figure(figsize=(8, 4))
    plt.plot(epochs_a, hist_a["train_loss"], label="smallcnn train loss")
    plt.plot(epochs_a, hist_a["val_loss"], label="smallcnn val loss")
    plt.plot(epochs_b, hist_b["train_loss"], label="resnet18 train loss")
    plt.plot(epochs_b, hist_b["val_loss"], label="resnet18 val loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Loss curves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(working_dir, out_name), dpi=160)
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.plot(epochs_a, hist_a["train_group_auc"], label="smallcnn train group AUC")
    plt.plot(epochs_a, hist_a["val_group_auc"], label="smallcnn val group AUC")
    plt.plot(epochs_b, hist_b["train_group_auc"], label="resnet18 train group AUC")
    plt.plot(epochs_b, hist_b["val_group_auc"], label="resnet18 val group AUC")
    plt.xlabel("Epoch")
    plt.ylabel("Group ROC-AUC")
    plt.title("Group-level ROC-AUC curves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(working_dir, out_name.replace("loss", "auc")), dpi=160)
    plt.close()


plot_learning_curves(
    res_a["history"], res_b["history"], out_name="learning_curves_loss_pcam_or_fallback.png"
)

# Save plottable histories
np.save(os.path.join(working_dir, "history_smallcnn.npy"), res_a["history"], allow_pickle=True)
np.save(os.path.join(working_dir, "history_resnet18.npy"), res_b["history"], allow_pickle=True)

# =====================
# Save experiment_data (MANDATORY)
# =====================
np.save(os.path.join(working_dir, "experiment_data.npy"), experiment_data, allow_pickle=True)

# =====================
# JSON summary (BUGFIX: sanitize numpy/tensor types)
# =====================
summary = {
    "dataset": experiment_data["pcam_or_fallback"]["meta"],
    "test_smallcnn": cev_a,
    "test_resnet18": cev_b,
}
summary_jsonable = to_jsonable(summary)
with open(os.path.join(working_dir, "summary.json"), "w") as f:
    json.dump(summary_jsonable, f, indent=2)

print("Done. Artifacts written to:", working_dir)
