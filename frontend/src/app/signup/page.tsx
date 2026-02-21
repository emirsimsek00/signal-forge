'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function SignupPage() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [displayName, setDisplayName] = useState('');
    const [workspaceName, setWorkspaceName] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    if (!isSupabaseConfigured) {
        if (typeof window !== 'undefined') router.replace('/');
        return null;
    }

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!supabase) return;
        setLoading(true);
        setError('');

        // 1. Create Supabase user
        const { data, error: signupError } = await supabase.auth.signUp({
            email,
            password,
            options: { data: { display_name: displayName } },
        });

        if (signupError) {
            setError(signupError.message);
            setLoading(false);
            return;
        }

        // 2. Create tenant + local user via backend callback
        if (data.user) {
            try {
                const res = await fetch(`${API_BASE}/api/auth/callback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        supabase_id: data.user.id,
                        email: data.user.email,
                        display_name: displayName || email.split('@')[0],
                        tenant_name: workspaceName || `${displayName || email.split('@')[0]}'s Workspace`,
                    }),
                });

                if (!res.ok) {
                    const err = await res.json();
                    setError(err.detail || 'Failed to create workspace');
                    setLoading(false);
                    return;
                }
            } catch {
                setError('Failed to connect to backend');
                setLoading(false);
                return;
            }
        }

        setSuccess(true);
        setLoading(false);
    };

    if (success) {
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
                    textAlign: 'center',
                    padding: 40,
                    background: 'rgba(255,255,255,0.04)',
                    backdropFilter: 'blur(20px)',
                    borderRadius: 20,
                    border: '1px solid rgba(255,255,255,0.08)',
                    maxWidth: 420,
                }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
                    <h2 style={{ color: '#f8fafc', fontSize: 22, fontWeight: 700 }}>Check your email</h2>
                    <p style={{ color: '#94a3b8', fontSize: 14, marginTop: 8 }}>
                        We sent a confirmation link to <strong style={{ color: '#e2e8f0' }}>{email}</strong>.
                        Click it to activate your account.
                    </p>
                    <a
                        href="/login"
                        style={{
                            display: 'inline-block',
                            marginTop: 24,
                            padding: '12px 24px',
                            borderRadius: 12,
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            color: '#fff',
                            textDecoration: 'none',
                            fontWeight: 600,
                        }}
                    >
                        Go to Login
                    </a>
                </div>
            </div>
        );
    }

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
                        Create your account
                    </h1>
                    <p style={{ color: '#94a3b8', fontSize: 14, marginTop: 8 }}>
                        Start monitoring signals in minutes
                    </p>
                </div>

                <form onSubmit={handleSignup}>
                    <div style={{ marginBottom: 16 }}>
                        <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                            Display Name
                        </label>
                        <input
                            type="text"
                            value={displayName}
                            onChange={e => setDisplayName(e.target.value)}
                            placeholder="Your name"
                            style={{
                                width: '100%', padding: '12px 16px', borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc', fontSize: 14, outline: 'none', boxSizing: 'border-box',
                            }}
                        />
                    </div>

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
                                width: '100%', padding: '12px 16px', borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc', fontSize: 14, outline: 'none', boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: 16 }}>
                        <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="Minimum 8 characters"
                            required
                            minLength={8}
                            style={{
                                width: '100%', padding: '12px 16px', borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc', fontSize: 14, outline: 'none', boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    <div style={{ marginBottom: 24 }}>
                        <label style={{ display: 'block', fontSize: 13, color: '#94a3b8', marginBottom: 6, fontWeight: 500 }}>
                            Workspace Name
                        </label>
                        <input
                            type="text"
                            value={workspaceName}
                            onChange={e => setWorkspaceName(e.target.value)}
                            placeholder="My Company"
                            style={{
                                width: '100%', padding: '12px 16px', borderRadius: 12,
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)',
                                color: '#f8fafc', fontSize: 14, outline: 'none', boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    {error && (
                        <div style={{
                            padding: '10px 14px', borderRadius: 10,
                            background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
                            color: '#fca5a5', fontSize: 13, marginBottom: 16,
                        }}>
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        style={{
                            width: '100%', padding: '14px 20px', borderRadius: 12, border: 'none',
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            color: '#fff', fontSize: 15, fontWeight: 600,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.7 : 1, transition: 'all 0.2s',
                        }}
                    >
                        {loading ? 'Creating account…' : 'Create account'}
                    </button>
                </form>

                <p style={{ textAlign: 'center', marginTop: 24, color: '#64748b', fontSize: 13 }}>
                    Already have an account?{' '}
                    <a href="/login" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 500 }}>
                        Sign in
                    </a>
                </p>
            </div>
        </div>
    );
}
