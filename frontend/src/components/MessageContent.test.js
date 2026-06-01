import { render, screen } from "@testing-library/react";
import MessageContent from "./MessageContent";

test("renders markdown links to open in a new tab", () => {
  render(<MessageContent content={"Read the [guide](https://www.partselect.com/repair/)"} />);

  const link = screen.getByRole("link", { name: "guide" });
  expect(link).toHaveAttribute("href", "https://www.partselect.com/repair/");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});
