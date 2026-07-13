import { AdminInviteActivation } from "@/app/components/admin-invite-activation"
import { PersonalSettings } from "@/app/components/personal-settings"
import { ProviderSettings } from "@/app/components/provider-settings"

export default function CabinetSettingsPage() {
  return <div className="space-y-10"><PersonalSettings /><ProviderSettings /><AdminInviteActivation /></div>
}
