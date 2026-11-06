// Source upload is the start page now; keep old links working.
import { redirect } from "next/navigation";

export default function UploadRedirect() {
  redirect("/");
}
