import React from "react";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

function addExternalLinkAttributes(html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("a").forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });
  return template.innerHTML;
}

export default function MessageContent({ content }) {
  if (!content) return null;
  const html = addExternalLinkAttributes(marked.parse(content));
  return (
    <div
      className="message-markdown"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
