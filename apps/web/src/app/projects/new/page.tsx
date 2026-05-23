import { AppHeader } from "@/components/AppHeader";
import { CreateProjectForm } from "@/components/CreateProjectForm";

export default function NewProjectPage() {
  return (
    <>
      <AppHeader />
      <main className="new-project">
        <p className="eyebrow">New creative</p>
        <h1>Compose products into a campaign</h1>
        <p className="lede">
          Supply one background and your brand assets. Qwen adjusts each product
          into the scene; logo and flag remain exact overlays.
        </p>
        <CreateProjectForm />
      </main>
    </>
  );
}
