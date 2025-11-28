import type { Components } from "react-markdown";

/* eslint-disable @typescript-eslint/no-explicit-any */
export const markdownComponents: Components = {
  h1: (props: any) => <h1 className="text-lg font-bold mb-2 mt-3 first:mt-0">{props.children}</h1>,
  h2: (props: any) => (
    <h2 className="text-base font-semibold mb-1 mt-2 first:mt-0">{props.children}</h2>
  ),
  h3: (props: any) => (
    <h3 className="text-base font-medium mb-1 mt-2 first:mt-0">{props.children}</h3>
  ),
  p: (props: any) => <p className="mb-1 last:mb-0">{props.children}</p>,
  ul: (props: any) => <ul className="list-disc ml-4 mb-1 space-y-0.5">{props.children}</ul>,
  ol: (props: any) => <ol className="list-decimal ml-4 mb-1 space-y-0.5">{props.children}</ol>,
  li: (props: any) => <li>{props.children}</li>,
  code: (props: any) => (
    <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{props.children}</code>
  ),
  pre: (props: any) => (
    <pre className="bg-muted p-2 rounded text-xs font-mono overflow-x-auto mb-1">
      {props.children}
    </pre>
  ),
  strong: (props: any) => <strong className="font-semibold">{props.children}</strong>,
  em: (props: any) => <em className="italic">{props.children}</em>,
  a: (props: any) => (
    <a
      href={props.href}
      className="text-primary hover:underline"
      target="_blank"
      rel="noopener noreferrer"
    >
      {props.children}
    </a>
  ),
};
/* eslint-enable @typescript-eslint/no-explicit-any */
