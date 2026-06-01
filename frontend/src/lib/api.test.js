import { parseSseBlock } from "./api";

test("parseSseBlock parses stage events", () => {
  expect(parseSseBlock('data: {"stage":"Understanding your request..."}')).toEqual({
    stage: "Understanding your request...",
  });
});

test("parseSseBlock ignores malformed events", () => {
  expect(parseSseBlock("event: ping")).toBeNull();
  expect(parseSseBlock("data: not-json")).toBeNull();
});
