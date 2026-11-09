type Metric = {
  label: string;
  value: string | number;
};

export function CreatorMetrics({ items }: { items: Metric[] }) {
  return (
    <dl
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
        gap: 0,
        margin: "0 0 24px",
        borderTop: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            padding: "12px 16px 12px 0",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <dd
            style={{
              margin: 0,
              fontSize: 24,
              fontWeight: 600,
              lineHeight: 1.2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {item.value}
          </dd>
          <dt className="fine" style={{ margin: "4px 0 0" }}>{item.label}</dt>
        </div>
      ))}
    </dl>
  );
}
