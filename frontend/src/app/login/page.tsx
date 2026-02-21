'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // If Supabase not configured, redirect to dashboard
    if (!isSupabaseConfigured) {
        if (typeof window !== 'undefined') router.replace('/');
        return null;
    }

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!supabase) return;
        setLoading(true);
        setError('');

        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) {
            setError(error.message);
            setLoading(false);
        } else {
            router.replace('/');
        }
    };

    const handleOAuth = async (provider: 'google' | 'github') => {
        if (!supabase) return;
        await supabase.auth.signInWithOAuth({
            provider,
            options: { redirectTo: `${window.location.origin}/` },
        });
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0a0a1a 100%)',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}>
            <div style={{
                width: '100%',
                maxWidth: 420,
                padding: 40,
                background: 'rgba(255,255,255,0.04)',
                backdropFilter: 'blur(20px)',
                borderRadius: 20,
                border: '1px solid rgba(255,255,255,0.08)',
                boxShadow: '0 25px 50px rgba(0,0,0,0.4)',
            }}>
                {/* Logo */}
                <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 56,
                        height: 56,
                        borderRadius: 16,
                        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                        marginBottom: 16,
                        fontSize: 28,
                    }}>
                        ⚡
                    </div>
                    <h1 style={{ color: '#f8fafc', fontSize: 24, fontWeight: 700, margin: 0 }}>
                        Welcome back
                    </h1>
                    <p style={{ color: '#94a3b8', fontSize: 14, marginTop: 8 }}>
                        Sign in to SignalForge
                    </p>
                </div>

                {/* OAuth buttons */}
                <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                    <button
                        onClick={() => handleOAuth('google')}
                        style={{
                            flex: 1,
                            padding: '12px 16px',
                            borderRadius: 12,
                            border: '1px solid rgba(255,255,255,0.1)',
                            background: 'rgba(255,255,255,0.05)',
                            color: '#e2e8f0',
                            cursor: 'pointer',
                            fontSize: 14,
                            fontWeight: 500,
                            transition: 'all 0.2s',
                        }}
                    >
                        🔷 Google
                    </button>
                    <button
                        onClick={() => handleOAuth('github')}
                        style={{
                            flex: 1,
                            padding: '12px 16px',
                            borderRadius: 12,
                            border: '1px solid rgba(255,255,255,0.1)',
                            background: 'rgba(255,255,255,0.05)',
                            color: '#e2e8f0',
                            cursor: 'pointer',
                            fontSize: 14,
                            fontWeight: 500,
                            transition: 'all 0.2s',
                        }}
                    >
                        🐙 GitHub
                    </button>
                </div>

                {/* Divider */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    marginBottom: 24,
                    color: '#475569',
                    fontSize: 13,
                }}>
                    <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
                    or
                    <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
                </div>

                {/* Email/password form */}
                <form onSubmit={handleLogin}>
                    <div style={{ marginBottom: 16 }}>
                        <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                            Email
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder="you@company.com"
                            required
                            style={{
                                width: '100%',
                                padding: '12px 16px',
                                borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)',
                                background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc',
                                fontSize: 14,
                                outline: 'none',
                                boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: 24 }}>
                        <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            minLength={8}
                            style={{
                                width: '100%',
                                padding: '12px 16px',
                                borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)',
                                background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc',
                                fontSize: 14,
                                outline: 'none',
                                boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    {error && (
                        <div style={{
                            padding: '10px 14px',
                            borderRadius: 10,
                            background: 'rgba(239,68,68,0.15)',
                            border: '1px solid rgba(239,68,68,0.3)',
                            color: '#fca5a5',
                            fontSize: 13,
                            marginBottom: 16,
                        }}>
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        style={{
                            width: '100%',
                            padding: '14px 20px',
                            borderRadius: 12,
                            border: 'none',
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            color: '#fff',
                            fontSize: 15,
                            fontWeight: 600,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.7 : 1,
                            transition: 'all 0.2s',
                        }}
                    >
                        {loading ? 'Signing in…' : 'Sign in'}
                    </button>
                </form>

                <p style={{ textAlign: 'center', marginTop: 24, color: '#64748b', fontSize: 13 }}>
                    Don&apos;t have an account?{' '}
                    <a href="/signup" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 500 }}>
                        Sign up
                    </a>
                </p>
            </div>
        </div>
    );
}
