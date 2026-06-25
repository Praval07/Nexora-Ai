import React, { useState } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Button, Card, Input } from '../components/Core';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [tab, setTab] = useState<'login' | 'register'>('login');
  
  // Login form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [subdomain, setSubdomain] = useState('');
  
  // Institution registration state
  const [instName, setInstName] = useState('');
  const [instSubdomain, setInstSubdomain] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [adminFirst, setAdminFirst] = useState('');
  const [adminLast, setAdminLast] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/auth/login', {
        email,
        password,
        subdomain,
      });
      const { access_token, refresh_token, user } = response.data.data;
      login(access_token, refresh_token, user);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      await api.post('/auth/register-institution', {
        name: instName,
        subdomain: instSubdomain,
        admin_email: adminEmail,
        admin_password: adminPassword,
        first_name: adminFirst,
        last_name: adminLast,
      });
      setSuccess('Institution registered successfully! You can now log in.');
      setTab('login');
      // Autofill subdomain
      setSubdomain(instSubdomain);
      setEmail(adminEmail);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Registration failed. Subdomain may be taken.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b0f19] px-4 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-indigo-900/10 rounded-full blur-[120px]" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-blue-900/10 rounded-full blur-[120px]" />

      <Card className="w-full max-w-md border-slate-800/80 bg-[#111827]/80 backdrop-blur-xl relative z-10">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
            Nexora AI
          </h1>
          <p className="text-slate-400 text-sm mt-2">
            Next-Gen Education Management Platform
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-slate-800 mb-6">
          <button
            onClick={() => { setTab('login'); setError(null); }}
            className={`flex-1 pb-3 text-sm font-semibold transition-all ${
              tab === 'login' ? 'border-b-2 border-indigo-500 text-indigo-400' : 'text-slate-400'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => { setTab('register'); setError(null); }}
            className={`flex-1 pb-3 text-sm font-semibold transition-all ${
              tab === 'register' ? 'border-b-2 border-indigo-500 text-indigo-400' : 'text-slate-400'
            }`}
          >
            Onboard Institution
          </button>
        </div>

        {error && (
          <div className="bg-red-950/40 border border-red-800/30 text-red-400 rounded-lg p-3 text-xs mb-4">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-emerald-950/40 border border-emerald-800/30 text-emerald-400 rounded-lg p-3 text-xs mb-4">
            {success}
          </div>
        )}

        {tab === 'login' ? (
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <Input
              id="subdomain"
              label="Institution Subdomain"
              placeholder="e.g. mit"
              value={subdomain}
              onChange={(e) => setSubdomain(e.target.value)}
              required
            />
            <Input
              id="email"
              label="Email Address"
              type="email"
              placeholder="admin@mit.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              id="password"
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Button type="submit" loading={loading} className="w-full mt-6">
              Access Portal
            </Button>
          </form>
        ) : (
          <form onSubmit={handleRegisterSubmit} className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            <Input
              id="instName"
              label="Institution Name"
              placeholder="e.g. MIT University"
              value={instName}
              onChange={(e) => setInstName(e.target.value)}
              required
            />
            <Input
              id="instSubdomain"
              label="Requested Subdomain"
              placeholder="e.g. mit"
              value={instSubdomain}
              onChange={(e) => setInstSubdomain(e.target.value)}
              required
            />
            <div className="border-t border-slate-800/50 my-4 pt-4">
              <p className="text-slate-400 font-semibold text-xs uppercase tracking-wider mb-3">
                Admin Profile Credentials
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  id="adminFirst"
                  label="First Name"
                  placeholder="John"
                  value={adminFirst}
                  onChange={(e) => setAdminFirst(e.target.value)}
                  required
                />
                <Input
                  id="adminLast"
                  label="Last Name"
                  placeholder="Doe"
                  value={adminLast}
                  onChange={(e) => setAdminLast(e.target.value)}
                  required
                />
              </div>
            </div>
            <Input
              id="adminEmail"
              label="Admin Email"
              type="email"
              placeholder="admin@institution.edu"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              required
            />
            <Input
              id="adminPassword"
              label="Admin Password"
              type="password"
              placeholder="Minimum 8 characters"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              required
            />
            <Button type="submit" loading={loading} className="w-full mt-6">
              Create ERP Instance
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
};
