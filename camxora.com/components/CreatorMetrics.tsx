import styles from "./creator-ui.module.css";

type Metric = {
  label: string;
  value: string | number;
};

export function CreatorMetrics({ items }: { items: Metric[] }) {
  return (
    <dl className={styles.metrics}>
      {items.map((item) => (
        <div className={styles.metric} key={item.label}>
          <dd className={styles.metricValue}>{item.value}</dd>
          <dt className={styles.metricLabel}>{item.label}</dt>
        </div>
      ))}
    </dl>
  );
}
