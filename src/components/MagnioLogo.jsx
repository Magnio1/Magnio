import { useId } from "react";

function MagnioLogo({ size = "default", className = "" }) {
  const sizes = {
    small: "h-8",
    default: "h-12",
    large: "h-20"
  };

  const gradientId = useId();

  return (
    <div className={`${sizes[size]} flex items-center gap-3 ${className}`}>
      {/* Icon/Symbol */}
      <svg className="h-full w-auto" viewBox="0 0 100 100">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#3B82F6" />
            <stop offset="50%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#EC4899" />
          </linearGradient>
        </defs>

        {/* M shape or abstract symbol */}
        <path
          d="M20 80 L20 20 L40 50 L60 20 L80 50 L80 80 M40 50 L40 80 M60 20 L60 50"
          stroke={`url(#${gradientId})`}
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {/* Text */}
      <span className="font-extrabold tracking-tight magnio-gradient-text text-2xl sm:text-3xl leading-none">
        MAGNIO
      </span>
    </div>
  );
}

export default MagnioLogo;
