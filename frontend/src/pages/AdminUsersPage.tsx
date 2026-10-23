import React, { useEffect, useState } from "react";
import { Users, UserPlus, Shield, X, Check, Lock } from "lucide-react";
import { api } from "../api/client";
import { UserProfile, UserRole } from "../types/api";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { useAuth } from "../context/AuthContext";
import { ForbiddenPage } from "./ForbiddenPage";

interface AdminUsersPageProps {
  onNavigate: (path: string) => void;
}

export const AdminUsersPage: React.FC<AdminUsersPageProps> = ({ onNavigate }) => {
  const { user, hasRole } = useAuth();
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New User Modal State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [newUsername, setNewUsername] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newRole, setNewRole] = useState<UserRole>("analyst");
  const [newFullName, setNewFullName] = useState<string>("");
  const [modalError, setModalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Authorization Guard: Admin Only
  if (!hasRole("admin")) {
    return <ForbiddenPage onNavigate={onNavigate} />;
  }

  const loadUsers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const list = await api.listUsers();
      setUsers(list);
    } catch (err: any) {
      setError(err.message || "Failed to retrieve user accounts.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    setIsSubmitting(true);
    try {
      await api.createUser({
        username: newUsername.trim(),
        password: newPassword,
        role: newRole,
        full_name: newFullName.trim() || undefined,
      });
      setIsModalOpen(false);
      setNewUsername("");
      setNewPassword("");
      setNewFullName("");
      await loadUsers();
    } catch (err: any) {
      setModalError(err.message || "Failed to create user account.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-wrapper">
      <div style={{ marginBottom: "2rem", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: "1.85rem", marginBottom: "0.35rem" }}>RBAC User Accounts</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Manage authenticated accounts and role-based permissions (Admin, Analyst, Planner, Viewer).
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => {
            setModalError(null);
            setIsModalOpen(true);
          }}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
        >
          <UserPlus size={16} />
          Provision New User
        </button>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Users Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Username</th>
              <th>Full Name</th>
              <th>Assigned RBAC Role</th>
              <th>Status</th>
              <th>Created At</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "3rem", color: "var(--text-muted)" }}>
                  Loading accounts...
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.user_id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-dim)" }}>
                    {u.user_id}
                  </td>
                  <td style={{ fontWeight: 600, color: "var(--text-main)" }}>{u.username}</td>
                  <td>{u.full_name || "&mdash;"}</td>
                  <td>
                    <span
                      className={`badge ${
                        u.role === "admin"
                          ? "badge-danger"
                          : u.role === "analyst"
                          ? "badge-info"
                          : u.role === "planner"
                          ? "badge-warning"
                          : "badge-neutral"
                      }`}
                    >
                      {u.role.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-success">Active</span>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    {u.created_at_utc.substring(0, 19).replace("T", " ")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Provision New User Modal */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
              <h3 style={{ fontSize: "1.2rem" }}>Provision New Account</h3>
              <button className="btn btn-ghost" onClick={() => setIsModalOpen(false)} style={{ padding: "0.3rem" }}>
                <X size={20} />
              </button>
            </div>

            {modalError && <Alert type="error">{modalError}</Alert>}

            <form onSubmit={handleCreateUser}>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input
                  type="text"
                  className="form-input"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                  placeholder="e.g. jdoe"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  placeholder="e.g. John Doe"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password (min 6 characters)</label>
                <input
                  type="password"
                  className="form-input"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder="Secure password"
                />
              </div>

              <div className="form-group">
                <label className="form-label">RBAC Role Assignment</label>
                <select
                  className="form-select"
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as UserRole)}
                >
                  <option value="analyst">Analyst (Forecasts, Model Evaluation, Exports)</option>
                  <option value="planner">Planner (Replenishment Simulation, Forecasts)</option>
                  <option value="viewer">Viewer (Read-only Dashboard &amp; SKUs)</option>
                  <option value="admin">Admin (Full System Management)</option>
                </select>
              </div>

              <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? "Provisioning..." : "Create User"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
