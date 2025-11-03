import argparse
import os
import sys
from datetime import datetime

from pymongo import MongoClient
from pymongo.database import Database

MONGODB_URL = os.environ.get("MONGODB_URL", "")


def connect_mongo() -> Database:
    if not MONGODB_URL:
        print("❌ MONGODB_URL environment variable not set", file=sys.stderr)
        sys.exit(1)

    client: MongoClient = MongoClient(MONGODB_URL)
    try:
        client.admin.command("ping")

        db_name = os.environ.get("MONGODB_DATABASE")

        if not db_name:
            if "/" in MONGODB_URL:
                parts = [p for p in MONGODB_URL.split("/") if p]
                if parts:
                    extracted = parts[-1].split("?")[0]
                    if extracted and not extracted.startswith("mongodb"):
                        db_name = extracted

        if not db_name:
            db_name = "ai_scientist"

        return client[db_name]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)


def list_runs(db: Database, status: str | None = None, limit: int = 10) -> None:
    runs_collection = db["runs"]

    query = {}
    if status:
        query["status"] = status

    runs = list(runs_collection.find(query).sort("createdAt", -1).limit(limit))

    if not runs:
        print("No runs found" + (f" with status '{status}'" if status else ""))
        return

    print(f"\n{'ID':<40} {'Status':<20} {'Claimed By':<20} {'Created':<20}")
    print("=" * 100)

    for run in runs:
        run_id = run["_id"]
        status = run["status"]
        claimed_by = run.get("claimedBy", "")[:18] if run.get("claimedBy") else "-"
        created = (
            run["createdAt"].strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(run["createdAt"], datetime)
            else str(run["createdAt"])
        )

        print(f"{run_id:<40} {status:<20} {claimed_by:<20} {created:<20}")

    print()


def show_run(db: Database, run_id: str) -> None:
    runs_collection = db["runs"]
    stages_collection = db["stages"]
    events_collection = db["events"]

    run = runs_collection.find_one({"_id": run_id})
    if not run:
        print(f"❌ Run not found: {run_id}")
        return

    print(f"\n{'=' * 60}")
    print(f"Run: {run_id}")
    print(f"{'=' * 60}\n")

    print(f"Status:       {run['status']}")
    print(f"Hypothesis:   {run['hypothesisId']}")
    print(f"Claimed By:   {run.get('claimedBy', '-')}")
    print(f"Created:      {run['createdAt']}")
    print(f"Updated:      {run.get('updatedAt', '-')}")
    print(f"Last Event:   #{run.get('lastEventSeq', 0)}")

    if run.get("currentStage"):
        stage = run["currentStage"]
        print(f"\nCurrent Stage: {stage.get('name', '-')}")
        print(f"Progress:      {stage.get('progress', 0) * 100:.1f}%")

    stages = list(stages_collection.find({"runId": run_id}).sort("index", 1))
    if stages:
        print(f"\n{'Stage':<15} {'Status':<15} {'Progress':<10}")
        print("-" * 40)
        for stage in stages:
            name = stage["name"]
            status = stage["status"]
            progress = f"{stage.get('progress', 0) * 100:.1f}%"
            print(f"{name:<15} {status:<15} {progress:<10}")

    event_count = events_collection.count_documents({"runId": run_id})
    print(f"\nTotal Events: {event_count}")

    if event_count > 0:
        recent_events = list(
            events_collection.find({"runId": run_id}).sort("timestamp", -1).limit(5)
        )
        print("\nRecent Events:")
        print("-" * 60)
        for event in recent_events:
            ts = (
                event["timestamp"].strftime("%H:%M:%S")
                if isinstance(event["timestamp"], datetime)
                else str(event["timestamp"])
            )
            event_type = event["type"].replace("ai.run.", "").replace("ai.", "")
            print(f"  {ts}  {event_type}")

    print()


def reset_run(db: Database, run_id: str) -> None:
    runs_collection = db["runs"]

    run = runs_collection.find_one({"_id": run_id})
    if not run:
        print(f"❌ Run not found: {run_id}")
        return

    result = runs_collection.update_one(
        {"_id": run_id},
        {
            "$set": {
                "status": "QUEUED",
                "claimedBy": None,
                "claimedAt": None,
                "lastEventSeq": 0,
                "currentStage": None,
                "updatedAt": datetime.utcnow(),
            }
        },
    )

    if result.modified_count > 0:
        print(f"✅ Reset run {run_id} to QUEUED")
    else:
        print(f"⚠ No changes made to run {run_id}")


def cancel_run(db: Database, run_id: str) -> None:
    runs_collection = db["runs"]

    run = runs_collection.find_one({"_id": run_id})
    if not run:
        print(f"❌ Run not found: {run_id}")
        return

    result = runs_collection.update_one(
        {"_id": run_id}, {"$set": {"status": "CANCELED", "updatedAt": datetime.utcnow()}}
    )

    if result.modified_count > 0:
        print(f"✅ Canceled run {run_id}")
    else:
        print(f"⚠ No changes made to run {run_id}")


def show_queue_stats(db: Database) -> None:
    runs_collection = db["runs"]

    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]

    stats = list(runs_collection.aggregate(pipeline))  # type: ignore[arg-type]

    print(f"\n{'=' * 60}")
    print("Queue Statistics")
    print(f"{'=' * 60}\n")

    total = 0
    for stat in stats:
        status = stat["_id"]
        count = stat["count"]
        total += count
        print(f"{status:<20} {count:>5}")

    print("-" * 60)
    print(f"{'TOTAL':<20} {total:>5}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage AI Scientist runs")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    list_parser = subparsers.add_parser("list", help="List runs")
    list_parser.add_argument("--status", type=str, help="Filter by status")
    list_parser.add_argument("--limit", type=int, default=10, help="Max runs to show")

    show_parser = subparsers.add_parser("show", help="Show run details")
    show_parser.add_argument("run_id", type=str, help="Run ID")

    reset_parser = subparsers.add_parser("reset", help="Reset run to QUEUED")
    reset_parser.add_argument("run_id", type=str, help="Run ID")

    cancel_parser = subparsers.add_parser("cancel", help="Cancel run")
    cancel_parser.add_argument("run_id", type=str, help="Run ID")

    subparsers.add_parser("stats", help="Show queue statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = connect_mongo()

    if args.command == "list":
        list_runs(db, status=args.status, limit=args.limit)
    elif args.command == "show":
        show_run(db, args.run_id)
    elif args.command == "reset":
        reset_run(db, args.run_id)
    elif args.command == "cancel":
        cancel_run(db, args.run_id)
    elif args.command == "stats":
        show_queue_stats(db)


if __name__ == "__main__":
    main()
