import React, { useState, useEffect } from "react";
import { useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ForecastPage } from "./pages/ForecastPage";
import { SkuExplorerPage } from "./pages/SkuExplorerPage";
import { ReplenishmentPage } from "./pages/ReplenishmentPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { HistoryPage } from "./pages/HistoryPage";
import { RegistryPage } from "./pages/RegistryPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { Navbar } from "./components/layout/Navbar";
import { GovernanceFooter } from "./components/layout/GovernanceFooter";

export const App: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentPath, setCurrentPath] = useState<string>(() => {
    return window.location.hash ? window.location.hash.replace("#", "") : "/";
  });

  useEffect(() => {
    const handleHashChange = () => {
      const path = window.location.hash ? window.location.hash.replace("#", "") : "/";
      setCurrentPath(path);
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navigate = (path: string) => {
    window.location.hash = path;
    setCurrentPath(path);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-dark)",
          color: "var(--text-muted)",
          fontSize: "1rem",
        }}
      >
        Initializing secure session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderCurrentPage = () => {
    switch (currentPath) {
      case "/":
        return <DashboardPage onNavigate={navigate} />;
      case "/forecast":
        return <ForecastPage />;
      case "/skus":
        return <SkuExplorerPage />;
      case "/planning":
        return <ReplenishmentPage />;
      case "/evaluation":
        return <EvaluationPage />;
      case "/history":
        return <HistoryPage />;
      case "/registry":
        return <RegistryPage />;
      case "/admin/users":
        return <AdminUsersPage onNavigate={navigate} />;
      default:
        return <DashboardPage onNavigate={navigate} />;
    }
  };

  return (
    <div className="app-container">
      <Navbar currentPath={currentPath} onNavigate={navigate} />
      <div className="main-content">
        <main style={{ flex: 1 }}>{renderCurrentPage()}</main>
        <GovernanceFooter />
      </div>
    </div>
  );
};
