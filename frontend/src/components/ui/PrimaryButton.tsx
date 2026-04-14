type PrimaryButtonProps = {
  children: React.ReactNode;
  fullWidth?: boolean;
  href?: string;
};

export default function PrimaryButton({
  children,
  fullWidth = true,
  href,
}: PrimaryButtonProps) {
  const className =
    "inline-flex h-12 items-center justify-center rounded-xl bg-[#135bec] px-5 font-semibold text-white shadow-sm transition hover:opacity-95";

  if (href) {
    return (
      <a href={href} className={`${className} ${fullWidth ? "w-full" : ""}`}>
        {children}
      </a>
    );
  }

  return <button className={`${className} ${fullWidth ? "w-full" : ""}`}>{children}</button>;
}