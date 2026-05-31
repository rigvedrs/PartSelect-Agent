import React from "react";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

export default function MessageContent({ content }) {
  if (!content) return null;
  const html = marked.parse(content);
  return (
    <div
      className="message-markdown"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
