import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatWidget from "./ChatWidget";
import { useSession } from "../hooks/useSession";
import { useChat } from "../hooks/useChat";
import { useCart } from "../hooks/useCart";

jest.mock("../hooks/useSession");
jest.mock("../hooks/useChat");
jest.mock("../hooks/useCart");

const send = jest.fn();
const startNewChat = jest.fn();

beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

beforeEach(() => {
  send.mockClear();
  startNewChat.mockClear();
  useSession.mockReturnValue({
    sessionId: "session-1",
    applianceModel: "",
    applianceModelForApi: "",
    setApplianceModel: jest.fn(),
    ensureSession: jest.fn(),
    startNewChat,
  });
  useChat.mockReturnValue({
    messages: [{ role: "assistant", content: "Welcome" }],
    isLoading: false,
    send,
  });
  useCart.mockReturnValue({
    cart: { count: 0, items: [] },
    refreshCart: jest.fn(),
    removeItem: jest.fn(),
  });
});

function openWidget() {
  render(<ChatWidget />);
  fireEvent.click(screen.getByRole("button", { name: "Open chat" }));
}

function sendMessage(text) {
  const input = screen.getByPlaceholderText("Ask about parts, compatibility, installation...");
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

test("disables input after 5 user messages and asks for a new chat", () => {
  openWidget();

  for (let i = 1; i <= 5; i += 1) {
    sendMessage(`message ${i}`);
  }

  expect(send).toHaveBeenCalledTimes(5);
  expect(screen.getByText("Message limit reached. Start a new chat to continue.")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Start a new chat to continue")).toBeDisabled();

  const disabledSendButton = screen.getByRole("button", { name: "Send" });
  expect(disabledSendButton).toBeDisabled();
});

test("new chat resets the message limit", async () => {
  startNewChat.mockResolvedValue(undefined);
  openWidget();

  for (let i = 1; i <= 5; i += 1) {
    sendMessage(`message ${i}`);
  }

  fireEvent.click(screen.getByRole("button", { name: "New chat" }));

  await waitFor(() => expect(startNewChat).toHaveBeenCalledTimes(1));
  await waitFor(() => {
    expect(screen.queryByText("Message limit reached. Start a new chat to continue.")).not.toBeInTheDocument();
  });
  expect(screen.getByPlaceholderText("Ask about parts, compatibility, installation...")).not.toBeDisabled();
});

test("expand button toggles the expanded panel class", () => {
  openWidget();

  const panel = screen.getByRole("dialog", { name: "PartSelect chat" });
  expect(panel).not.toHaveClass("expanded");

  fireEvent.click(screen.getByRole("button", { name: "Expand chat" }));
  expect(panel).toHaveClass("expanded");

  fireEvent.click(screen.getByRole("button", { name: "Collapse chat" }));
  expect(panel).not.toHaveClass("expanded");
});
