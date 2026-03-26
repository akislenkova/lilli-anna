import { useState } from "react";
import { DisclaimerModal } from "../components/common/DisclaimerModal";
import { IntakeFlow } from "../components/patient/IntakeFlow";

export function IntakePage() {
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false);

  if (!disclaimerAccepted) {
    return (
      <DisclaimerModal
        onAccept={() => setDisclaimerAccepted(true)}
        onDecline={() => window.history.back()}
      />
    );
  }

  return <IntakeFlow />;
}
