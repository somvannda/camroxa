import { describe, expect, it } from "vitest";

import {
  DESIGN_CARD_SUBTITLE,
  designPlugin,
  familyForPrompt,
  nameForPrompt,
} from "@/lib/studio-designer";
import {
  addCustomPlugin,
  sanitizeChain,
  setParam,
} from "@/lib/studio-plugin-chain";
import { sanitizeCustomPlugin } from "@/lib/studio-plugins";

const CAPTURED =
  "A warm tape saturation plugin with gentle drive and a low cut";

describe("plugin designer (S45)", () => {
  it("names the plugin from the description", () => {
    expect(nameForPrompt(CAPTURED, "saturation")).toBe("Warm Tape");
  });

  it("picks the saturation family from warm/tape/drive words", () => {
    expect(familyForPrompt(CAPTURED)).toBe("saturation");
    expect(familyForPrompt("a lush cathedral reverb")).toBe("space");
    expect(familyForPrompt("a slow chorus wobble")).toBe("movement");
    expect(familyForPrompt("glue the vocal with gentle compression")).toBe("dynamics");
    expect(familyForPrompt("cut the mud with a high pass")).toBe("filter");
  });

  it("restates the request and asks before building", () => {
    const { plugin, restate, completion } = designPlugin(CAPTURED);
    expect(plugin.name).toBe("Warm Tape");
    expect(plugin.family).toBe("saturation");
    expect(restate).toContain("warm tape-saturation audio effect");
    expect(restate).toContain("saved to your plugin library");
    expect(restate.endsWith("Build it?")).toBe(true);
    expect(completion).toContain("Warm Tape is ready");
    expect(DESIGN_CARD_SUBTITLE).toBe("Audio effect · Drag onto a track");
  });

  it("derives controls from the prompt (gentle drive, low cut)", () => {
    const { plugin } = designPlugin(CAPTURED);
    const drive = plugin.params.find((param) => param.key === "drive");
    const lowCut = plugin.params.find((param) => param.key === "lowCut");
    expect(drive?.default).toBe(26);
    expect(lowCut?.default).toBe(140);
    expect(plugin.defaults.drive).toBe(26);
  });

  it("is deterministic and avoids duplicate names", () => {
    const a = designPlugin(CAPTURED);
    const b = designPlugin(CAPTURED);
    expect(a.plugin.id).toBe(b.plugin.id);
    const c = designPlugin(CAPTURED, ["Warm Tape"]);
    expect(c.plugin.name).toBe("Warm Tape 2");
    expect(c.plugin.id).not.toBe(a.plugin.id);
  });

  it("round-trips through a sanitized chain", () => {
    const { plugin } = designPlugin(CAPTURED);
    const chain = addCustomPlugin([], plugin);
    expect(chain).toHaveLength(1);
    expect(chain[0].pluginId).toBe("custom");
    expect(chain[0].custom?.name).toBe("Warm Tape");

    const louder = setParam(chain, chain[0].entryId, "drive", 999);
    expect(louder[0].params.drive).toBe(100);

    const restored = sanitizeChain(JSON.parse(JSON.stringify(chain)));
    expect(restored).toHaveLength(1);
    expect(restored[0].custom?.name).toBe("Warm Tape");
    expect(restored[0].params.drive).toBe(26);
  });

  it("rejects a malformed designed-plugin snapshot", () => {
    expect(sanitizeCustomPlugin({ id: "custom-x", name: "X", family: "nope", params: [] })).toBeNull();
    expect(
      sanitizeCustomPlugin({
        id: "builtin",
        name: "X",
        family: "filter",
        params: [{ key: "a", label: "A", min: 0, max: 1, default: 0 }],
      })
    ).toBeNull();
  });
});
