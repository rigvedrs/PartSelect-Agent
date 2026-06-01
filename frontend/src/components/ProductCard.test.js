import { render, screen } from "@testing-library/react";
import ProductCard from "./ProductCard";

const basePart = {
  ps_number: "PS11752778",
  name: "Refrigerator Door Shelf Bin",
  price: 47.4,
};

test("does not render an image placeholder when image_url is missing", () => {
  render(<ProductCard part={basePart} />);

  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByText(/no image/i)).not.toBeInTheDocument();
});

test("renders the part image when image_url is present", () => {
  render(<ProductCard part={{ ...basePart, image_url: "https://example.test/bin.jpg" }} />);

  expect(screen.getByRole("img", { name: basePart.name })).toHaveAttribute(
    "src",
    "https://example.test/bin.jpg",
  );
});
