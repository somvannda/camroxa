import { describe, expect, it } from "vitest";

import { addPlugin, sanitizeChain, setSidechain } from "@/lib/studio-plugin-chain";

describe("compressor sidechain (S43)", () => {
  it("stores and restores a valid pre/post key", () => {
    const chain = addPlugin([], "compressor");
    const keyed = setSidechain(chain, chain[0].entryId, { trackId: "track-2", tap: "post" });
    expect(keyed[0].sidechain).toEqual({ trackId: "track-2", tap: "post" });

    const restored = sanitizeChain(JSON.parse(JSON.stringify(keyed)));
    expect(restored[0].sidechain).toEqual({ trackId: "track-2", tap: "post" });
  });

  it("drops a malformed key instead of trusting it", () => {
    const chain = addPlugin([], "compressor");
    const broken = JSON.parse(JSON.stringify(chain)) as Array<Record<string, unknown>>;
    broken[0].sidechain = { trackId: "", tap: "sideways" };
    expect(sanitizeChain(broken)[0].sidechain).toBeNull();
  });

  it("clears the key with null", () => {
    const chain = addPlugin([], "compressor");
    const keyed = setSidechain(chain, chain[0].entryId, { trackId: "track-2", tap: "pre" });
    const cleared = setSidechain(keyed, chain[0].entryId, null);
    expect(cleared[0].sidechain).toBeNull();
  });
});
