import { ServiceEditor } from "@/app/components/service-editor"
import { Search } from "@/app/components/search-interface"
import { editorRuntimeProfile } from "@/lib/editor-adapter"

export default function Home() {
  if (editorRuntimeProfile() === "service") return <ServiceEditor />
  return <div className="flex h-screen w-full"><Search /></div>
}
