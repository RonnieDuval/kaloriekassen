const LOCAL_CALLBACK_URL = "http://localhost:8081/";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // Withings verifies the registered URL with an HTTP HEAD request.
    if (request.method === "HEAD" && url.pathname === "/oauth/callback") {
      return new Response(null, { status: 200, headers: NO_STORE_HEADERS });
    }

    if (request.method === "GET" && url.pathname === "/oauth/callback") {
      const destination = new URL(LOCAL_CALLBACK_URL);
      for (const key of ["code", "state", "error", "error_description"]) {
        const value = url.searchParams.get(key);
        if (value !== null) destination.searchParams.set(key, value);
      }

      if (!destination.searchParams.has("state")) {
        return new Response("Missing OAuth state", {
          status: 400,
          headers: { ...NO_STORE_HEADERS, "Content-Type": "text/plain; charset=utf-8" },
        });
      }

      return new Response(null, {
        status: 302,
        headers: { ...NO_STORE_HEADERS, Location: destination.toString() },
      });
    }

    return new Response("Withings OAuth relay is ready.", {
      status: 200,
      headers: { ...NO_STORE_HEADERS, "Content-Type": "text/plain; charset=utf-8" },
    });
  },
};
