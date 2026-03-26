import { useState } from "react";

interface Props {
  open: boolean;
  onAccept: () => void;
  onDecline: () => void;
}

export default function DisclaimerModal({ open, onAccept, onDecline }: Props) {
  const [checked, setChecked] = useState(false);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-gray-200 px-6 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
            <svg
              className="h-5 w-5 text-primary-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900">
            Important Information
          </h2>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-5">
          <p className="text-sm leading-relaxed text-gray-700">
            Please read the following carefully before proceeding with the
            intake questionnaire.
          </p>

          <div className="space-y-3 rounded-lg bg-blue-50 p-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-200 text-xs font-bold text-blue-800">
                1
              </div>
              <p className="text-sm text-gray-800">
                This AI is an <strong>administrative scheduling assistant</strong>,
                not a physician. It does not provide medical advice or diagnoses.
              </p>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-200 text-xs font-bold text-blue-800">
                2
              </div>
              <p className="text-sm text-gray-800">
                The questions asked are used solely to help estimate appointment
                duration and prepare your physician. They are{" "}
                <strong>not a diagnosis</strong>.
              </p>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-200 text-xs font-bold text-blue-800">
                3
              </div>
              <p className="text-sm text-gray-800">
                If you are experiencing an <strong>acute medical emergency</strong>,
                please close this form and contact emergency services (911)
                immediately.
              </p>
            </div>
          </div>

          {/* Checkbox */}
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">
              I understand that this AI assistant does not provide medical
              diagnoses, and I should contact emergency services for acute
              emergencies.
            </span>
          </label>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4">
          <button
            onClick={onDecline}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onAccept}
            disabled={!checked}
            className="rounded-lg bg-primary-600 px-5 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            I Understand, Continue
          </button>
        </div>
      </div>
    </div>
  );
}
