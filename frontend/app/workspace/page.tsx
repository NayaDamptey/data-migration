import { redirect } from "next/navigation";

// Setup now lives on the start page (Source & setup).
export default function WorkspacePage() {
  redirect("/");
}
