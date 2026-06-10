import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata = {
  title: "BeeBI Intelligence Suite",
  description: "Data profiling and ML-readiness tooling on Databricks — by BeeBI.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1200px] px-6 py-6 lg:px-10 lg:py-8">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
