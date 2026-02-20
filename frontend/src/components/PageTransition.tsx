"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * Wraps page content with a smooth fade-in-up animation on route changes.
 * Also applies stagger animation to direct children for a cascading feel.
 */
export default function PageTransition({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const [key, setKey] = useState(pathname);

    useEffect(() => {
        setKey(pathname);
    }, [pathname]);

    return (
        <div key={key} className="page-transition stagger-children">
            {children}
        </div>
    );
}
