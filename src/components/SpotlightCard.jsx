import { useRef, useState } from "react";

const SpotlightCard = ({ children, className = "" }) => {
    const divRef = useRef(null);
    const [isFocused, setIsFocused] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [opacity, setOpacity] = useState(0);

    const handleMouseMove = (e) => {
        if (!divRef.current) return;

        const div = divRef.current;
        const rect = div.getBoundingClientRect();

        setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    };

    const handleFocus = () => {
        setIsFocused(true);
        setOpacity(1);
    };

    const handleBlur = () => {
        setIsFocused(false);
        setOpacity(0);
    };

    const handleMouseEnter = () => {
        setOpacity(1);
    };

    const handleMouseLeave = () => {
        setOpacity(0);
    };

    return (
        <div
            ref={divRef}
            onMouseMove={handleMouseMove}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            className={`relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 ${className}`}
        >
            <div
                className="pointer-events-none absolute -inset-px opacity-0 transition duration-300"
                style={{
                    opacity,
                    background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, rgba(59, 130, 246, 0.15), transparent 40%)`,
                }}
            />
            <div
                className="pointer-events-none absolute -inset-px opacity-0 transition duration-300"
                style={{
                    opacity,
                    background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, rgba(59, 130, 246, 0.1), transparent 40%)`,
                    maskImage: `radial-gradient(400px circle at ${position.x}px ${position.y}px, black, transparent)`,
                    WebkitMaskImage: `radial-gradient(400px circle at ${position.x}px ${position.y}px, black, transparent)`,
                    // Mask the border only
                    maskComposite: "exclude",
                    WebkitMaskComposite: "xor",
                    padding: "1px",
                }}
            // This second div logic is complicated to get just the border glow right without SVG.
            // Let's simplify: A spotlight overlay on the background is usually enough for the "spotlight" effect on the surface.
            // For the border glow, we can use a slightly different technique or just stick to the surface glow for now which is very modern.
            // Actually, the "Spotlight" usually implies that the *border* reveals itself.
            // Let's try a simpler approach for the implementation:
            // 1. Background glow (already added above)
            // 2. An overlay that lights up the border?
            />
            {/* 
         Better border glow approach:
         Use a "before" element for the border that is masked by the content? 
         Or just a gradient that moves? 
         Let's stick to the surface glow for now, it's safer and looks great.
      */}
            <div className="relative h-full">{children}</div>
        </div>
    );
};

export default SpotlightCard;
