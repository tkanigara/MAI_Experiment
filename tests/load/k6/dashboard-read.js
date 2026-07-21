import http from "k6/http";
import { check, group, sleep } from "k6";


const BASE_URL = (__ENV.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const TEST_TYPE = (__ENV.TEST_TYPE || "smoke").toLowerCase();
const CLIENT_CODE = (__ENV.CLIENT_CODE || "").trim().toLowerCase();
const THINK_TIME_SECONDS = Number(__ENV.THINK_TIME_SECONDS || 1);
const READ_P95_MS = Number(__ENV.READ_P95_MS || 1000);
const OVERVIEW_P95_MS = Number(__ENV.OVERVIEW_P95_MS || 1500);

const PROFILES = {
  smoke: {
    executor: "constant-vus",
    vus: 1,
    duration: "20s",
  },
  load: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "30s", target: 5 },
      { duration: "2m", target: 10 },
      { duration: "30s", target: 0 },
    ],
    gracefulRampDown: "15s",
  },
  stress: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "30s", target: 10 },
      { duration: "1m", target: 25 },
      { duration: "1m", target: 50 },
      { duration: "1m", target: 75 },
      { duration: "30s", target: 0 },
    ],
    gracefulRampDown: "15s",
  },
  spike: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "10s", target: 5 },
      { duration: "10s", target: 80 },
      { duration: "30s", target: 80 },
      { duration: "20s", target: 0 },
    ],
    gracefulRampDown: "10s",
  },
  soak: {
    executor: "constant-vus",
    vus: 10,
    duration: "30m",
  },
  custom: {
    executor: "constant-vus",
    vus: Number(__ENV.K6_VUS || 10),
    duration: __ENV.K6_DURATION || "5m",
  },
};

if (!PROFILES[TEST_TYPE]) {
  throw new Error(
    `Unknown TEST_TYPE '${TEST_TYPE}'. Use smoke, load, stress, spike, soak, or custom.`,
  );
}

export const options = {
  scenarios: {
    dashboard_reads: {
      ...PROFILES[TEST_TYPE],
      exec: "dashboardReads",
      tags: { suite: "dashboard-read", test_type: TEST_TYPE },
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    [`http_req_duration{endpoint:clients}`]: [`p(95)<${READ_P95_MS}`],
    [`http_req_duration{endpoint:platforms}`]: [`p(95)<${READ_P95_MS}`],
    [`http_req_duration{endpoint:overview}`]: [`p(95)<${OVERVIEW_P95_MS}`],
  },
};

function requestTags(endpoint) {
  return {
    tags: { endpoint },
    timeout: "10s",
  };
}

function isJson(response) {
  const contentType = response.headers["Content-Type"] || "";
  return contentType.toLowerCase().includes("application/json");
}

function parseJson(response, label) {
  if (!isJson(response)) {
    throw new Error(`${label} did not return JSON (status ${response.status}).`);
  }

  try {
    return response.json();
  } catch (error) {
    throw new Error(`${label} returned invalid JSON: ${error.message}`);
  }
}

function connectedPlatforms(client, profiles) {
  const supported = ["instagram", "facebook", "tiktok", "youtube"];
  const result = new Set();

  for (const platform of supported) {
    if (client[`has_${platform}`]) {
      result.add(platform);
    }
  }

  for (const profile of profiles || []) {
    if (supported.includes(profile.platform)) {
      result.add(profile.platform);
    }
  }

  return [...result];
}

export function setup() {
  const clientsResponse = http.get(
    `${BASE_URL}/api/clients`,
    requestTags("setup-clients"),
  );

  if (clientsResponse.status !== 200) {
    throw new Error(
      `Cannot prepare load test: GET /api/clients returned ${clientsResponse.status}.`,
    );
  }

  const clients = parseJson(clientsResponse, "GET /api/clients");
  if (!Array.isArray(clients) || clients.length === 0) {
    throw new Error("Cannot prepare load test: no active clients are available.");
  }

  const client = CLIENT_CODE
    ? clients.find((item) => String(item.client_code || "").toLowerCase() === CLIENT_CODE)
    : clients[0];

  if (!client) {
    throw new Error(`Cannot prepare load test: client '${CLIENT_CODE}' was not found.`);
  }

  const platformsResponse = http.get(
    `${BASE_URL}/api/clients/${encodeURIComponent(client.id)}/platforms`,
    requestTags("setup-platforms"),
  );

  if (platformsResponse.status !== 200) {
    throw new Error(
      `Cannot prepare load test: client platforms returned ${platformsResponse.status}.`,
    );
  }

  const platformPayload = parseJson(platformsResponse, "GET client platforms");
  const platforms = connectedPlatforms(platformPayload.client || client, platformPayload.profiles);
  if (platforms.length === 0) {
    throw new Error(`Cannot prepare load test: client '${client.client_code}' has no platforms.`);
  }

  const reportMonths = Array.isArray(platformPayload.report_months)
    ? platformPayload.report_months
    : [];

  return {
    clientId: String(client.id),
    clientCode: String(client.client_code),
    platforms,
    periodId: reportMonths.length > 0 ? String(reportMonths[0].id) : "",
  };
}

export function dashboardReads(data) {
  group("clients list", () => {
    const response = http.get(`${BASE_URL}/api/clients`, requestTags("clients"));
    check(response, {
      "clients status is 200": (result) => result.status === 200,
      "clients response is JSON": isJson,
    });
  });

  group("client platforms", () => {
    const response = http.get(
      `${BASE_URL}/api/clients/${encodeURIComponent(data.clientId)}/platforms`,
      requestTags("platforms"),
    );
    check(response, {
      "platforms status is 200": (result) => result.status === 200,
      "platforms response is JSON": isJson,
    });
  });

  group("platform overview", () => {
    const platformIndex = (__VU + __ITER) % data.platforms.length;
    const platform = data.platforms[platformIndex];
    const periodQuery = data.periodId
      ? `?period_id=${encodeURIComponent(data.periodId)}`
      : "";
    const response = http.get(
      `${BASE_URL}/api/clients/${encodeURIComponent(data.clientId)}`
        + `/platforms/${encodeURIComponent(platform)}/overview${periodQuery}`,
      requestTags("overview"),
    );
    check(response, {
      "overview status is 200": (result) => result.status === 200,
      "overview response is JSON": isJson,
      "overview has requested platform": (result) => {
        if (!isJson(result) || result.status !== 200) {
          return false;
        }
        try {
          const payload = result.json();
          return payload.platform === platform || payload.report?.platform === platform;
        } catch (_error) {
          return false;
        }
      },
    });
  });

  if (THINK_TIME_SECONDS > 0) {
    sleep(THINK_TIME_SECONDS);
  }
}
