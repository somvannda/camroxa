import { describe, expect, it } from "vitest";

import {
  DESIGN_CARD_SUBTITLE,
  familyForPrompt,
  pluginFromAuthoring,
  restateDesign,
  type AuthoredPluginDescriptor,
} from "@/lib/studio-designer";
import { addCustomPlugin, sanitizeChain, setParam } from "@/lib/studio-plugin-chain";
import { sanitizeCustomPlugin } from "@/lib/studio-plugins";

const CAPTURED = "A warm tape saturation plugin with gentle drive and a low cut";

const DESCRIPTOR: AuthoredPluginDescriptor = {
  displayName: "Gentle High-Pass",
  description: "A smooth stereo high-pass filter for clearing low-end rumble.",
  kind: "effect",
  parameters: [
    { name: "Cutoff", label: "Cutoff", default: 120, range: { min: 20, max: 2000 }, scale: "log", unit: "hz" },
    { name: "Mix", label: "Mix", default: 0.5, range: { min: 0, max: 1 }, scale: "linear", unit: "percent" },
    { name: "Drive", label: "Drive", default: 0.2, range: { min: 0, max: 1 }, unit: "percent" },
    { name: "Attack", label: "Attack", default: 5, range: { min: 0, max: 100 }, unit: "ms" },
  ],
};

const IDS = { pluginId: "10c35bed-09ff-4bfe-86a8-f386bc281934", pluginVersionId: "53004c03-2451-47d2-957a-3acac99a626a" };

describe("plugin designer (S45, Suno authoring agent)", () => {
  it("picks the family for the local audio approximation", () => {
    expect(familyForPrompt(CAPTURED)).toBe("saturation");
    expect(familyForPrompt("a lush cathedral reverb")).toBe("space");
    expect(familyForPrompt("a slow chorus wobble")).toBe("movement");
    expect(familyForPrompt("glue the vocal with gentle compression")).toBe("dynamics");
    expect(familyForPrompt("cut the mud with a high pass")).toBe("filter");
  });

  it("restates the request and asks before spending credits", () => {
    const restate = restateDesign(CAPTURED);
    expect(restate).toContain("plugin agent");
    expect(restate).toContain("saved to your plugin library");
    expect(restate.endsWith("Build it?")).toBe(true);
    expect(DESIGN_CARD_SUBTITLE).toBe("Audio effect · Drag onto a track");
  });

  it("converts the agent descriptor into a designed plugin", () => {
    const plugin = pluginFromAuthoring(DESCRIPTOR, { instruction: CAPTURED, ...IDS });
    expect(plugin).not.toBeNull();
    if (!plugin) return;
    expect(plugin.name).toBe("Gentle High-Pass");
    expect(plugin.family).toBe("filter");
    expect(plugin.sunoPluginId).toBe(IDS.pluginId);
    expect(plugin.sunoPluginVersionId).toBe(IDS.pluginVersionId);
    expect(plugin.params.map((param) => param.key)).toEqual(["Cutoff", "Mix", "Drive", "Attack"]);
    expect(plugin.params[0]).toMatchObject({ min: 20, max: 2000, default: 120, unit: "hz", tier: "primary" });
    // Percent controls keep Suno's 0–1 range; the knob renders it as 0–100 %.
    expect(plugin.params[1]).toMatchObject({ min: 0, max: 1, default: 0.5, unit: "%" });
    expect(plugin.params[3].tier).toBe("secondary");
    expect(plugin.defaults.Cutoff).toBe(120);
  });

  it("renames a duplicate so MY PLUGINS stays readable", () => {
    const plugin = pluginFromAuthoring(DESCRIPTOR, {
      instruction: CAPTURED,
      existingNames: ["Gentle High-Pass"],
      ...IDS,
    });
    expect(plugin?.name).toBe("Gentle High-Pass 2");
  });

  it("rejects a descriptor with no usable controls", () => {
    expect(
      pluginFromAuthoring({ displayName: "Empty", parameters: [] }, { instruction: CAPTURED, ...IDS })
    ).toBeNull();
    expect(
      pluginFromAuthoring(
        { displayName: "Broken", parameters: [{ name: "X", range: { min: 1, max: 1 } }] },
        { instruction: CAPTURED, ...IDS }
      )
    ).toBeNull();
  });

  it("round-trips through a sanitized chain with the Suno ids intact", () => {
    const plugin = pluginFromAuthoring(DESCRIPTOR, { instruction: CAPTURED, ...IDS });
    expect(plugin).not.toBeNull();
    if (!plugin) return;
    const chain = addCustomPlugin([], plugin);
    expect(chain).toHaveLength(1);
    expect(chain[0].pluginId).toBe("custom");
    expect(chain[0].custom?.sunoPluginId).toBe(IDS.pluginId);

    const louder = setParam(chain, chain[0].entryId, "Mix", 9);
    expect(louder[0].params.Mix).toBe(1);

    const restored = sanitizeChain(JSON.parse(JSON.stringify(chain)));
    expect(restored).toHaveLength(1);
    expect(restored[0].custom?.sunoPluginVersionId).toBe(IDS.pluginVersionId);
    expect(restored[0].params.Mix).toBe(0.5);
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
