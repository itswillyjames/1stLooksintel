import { useState } from "react";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { PermitsList } from "@/components/PermitsList";
import { PermitDetail } from "@/components/PermitDetail";

function App() {
  const [selectedPermit, setSelectedPermit] = useState(null);

  return (
    <div className="min-h-screen bg-background">
      <Toaster position="top-right" />
      
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-3">
          <h1 className="text-xl font-bold text-foreground" data-testid="app-title">
            Permit Intel
          </h1>
          <p className="text-sm text-muted-foreground">
            Single-operator permit intelligence workbench
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {selectedPermit ? (
          <PermitDetail 
            permit={selectedPermit} 
            onBack={() => setSelectedPermit(null)} 
          />
        ) : (
          <PermitsList onSelectPermit={setSelectedPermit} />
        )}
      </main>
    </div>
  );
}

export default App;
