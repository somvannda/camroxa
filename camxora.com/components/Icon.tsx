type IconProps = {
  name: string;
  className?: string;
};

export function Icon({ name, className = "" }: IconProps) {
  return (
    <i
      className={`icon fa-classic fa-solid fa-replaced ${name} ${className}`.trim()}
      aria-hidden="true"
    />
  );
}
