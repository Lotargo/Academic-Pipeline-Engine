import { AdminInviteActivation } from "@/app/components/admin-invite-activation"
import { ProviderSettings } from "@/app/components/provider-settings"

export default function CabinetSettingsPage() {
  return <div className="space-y-6"><ProviderSettings /><AdminInviteActivation /></div>
}
