jest.mock("react-dom/client", () => ({
  createRoot: jest.fn(() => ({ render: jest.fn() })),
}));

jest.mock("./reportWebVitals", () => jest.fn());
jest.mock("./App", () => function MockApp() { return <div>App demo</div>; });
jest.mock("./components/ChatWidget", () => function MockChatWidget() { return <div>Widget</div>; });

function loadIndexWithHtml(html) {
  let client;
  document.body.innerHTML = html;
  jest.isolateModules(() => {
    client = require("react-dom/client");
    require("./index");
  });
  return client;
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("mounts ChatWidget when an embed mount node is present", () => {
  const client = loadIndexWithHtml('<div id="partselect-chat-widget"></div>');

  expect(client.createRoot).toHaveBeenCalledWith(
    document.getElementById("partselect-chat-widget")
  );
});

test("falls back to the demo app root when no embed mount node is present", () => {
  const client = loadIndexWithHtml('<div id="root"></div>');

  expect(client.createRoot).toHaveBeenCalledWith(
    document.getElementById("root")
  );
});
