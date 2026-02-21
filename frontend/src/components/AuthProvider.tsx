'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { User, Session } from '@supabase/supabase-js';

interface AuthContextType {
    user: User | null;
    session: Session | null;
    loading: boolean;
    isDemo: boolean;
    signOut: () => Promise<void>;
    tenant: { id: string; name: string; slug: string } | null;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    session: null,
    loading: true,
    isDemo: true,
    signOut: async () => { },
    tenant: null,
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);
    const [tenant, setTenant] = useState<AuthContextType['tenant']>(null);

    const isDemo = !isSupabaseConfigured;

    useEffect(() => {
        if (!supabase) {
            // Demo mode — no auth needed
            setLoading(false);
            setTenant({ id: 'default', name: 'Demo Workspace', slug: 'demo' });
            return;
        }

        // Get initial session
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session);
            setUser(session?.user ?? null);
            if (session?.user) {
                fetchTenant(session.access_token);
            }
            setLoading(false);
        });

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (_event, session) => {
                setSession(session);
                setUser(session?.user ?? null);
                if (session?.user) {
                    fetchTenant(session.access_token);
                } else {
                    setTenant(null);
                }
            }
        );

        return () => subscription.unsubscribe();
    }, []);

    const fetchTenant = useCallback(async (accessToken: string) => {
        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const res = await fetch(`${API_BASE}/api/auth/me`, {
                headers: { Authorization: `Bearer ${accessToken}` },
            });
            if (res.ok) {
                const data = await res.json();
                setTenant(data.tenant);
            }
        } catch {
            // Silently fail — tenant info is non-critical
        }
    }, []);

    const signOut = useCallback(async () => {
        if (supabase) {
            await supabase.auth.signOut();
        }
        setUser(null);
        setSession(null);
        setTenant(null);
    }, []);

    return (
        <AuthContext.Provider value={{ user, session, loading, isDemo, signOut, tenant }}>
            {children}
        </AuthContext.Provider>
    );
}
