import api from "./api";
import type { ConversationSession, VisitType } from "../types";

export async function startConversation(
  visitType: VisitType,
  disclaimerAccepted: boolean,
): Promise<ConversationSession> {
  const { data } = await api.post<{ data: ConversationSession }>(
    "/conversations",
    {
      visit_type: visitType,
      disclaimer_accepted: disclaimerAccepted,
    },
  );
  return data.data;
}

export async function submitAnswer(
  sessionId: string,
  answer: string,
): Promise<ConversationSession> {
  const { data } = await api.post<{ data: ConversationSession }>(
    `/conversations/${sessionId}/answer`,
    { answer },
  );
  return data.data;
}

export async function uploadVoiceNote(
  sessionId: string,
  audioBlob: Blob,
): Promise<ConversationSession> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "voice_note.webm");

  const { data } = await api.post<{ data: ConversationSession }>(
    `/conversations/${sessionId}/voice`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data.data;
}

export async function confirmTranscript(
  sessionId: string,
  confirmed: boolean,
): Promise<ConversationSession> {
  const { data } = await api.post<{ data: ConversationSession }>(
    `/conversations/${sessionId}/confirm-transcript`,
    { confirmed },
  );
  return data.data;
}

export async function rankConcerns(
  sessionId: string,
  concerns: string[],
): Promise<ConversationSession> {
  const { data } = await api.post<{ data: ConversationSession }>(
    `/conversations/${sessionId}/rank-concerns`,
    { concerns },
  );
  return data.data;
}

export async function getConversation(
  sessionId: string,
): Promise<ConversationSession> {
  const { data } = await api.get<{ data: ConversationSession }>(
    `/conversations/${sessionId}`,
  );
  return data.data;
}

export async function completeConversation(
  sessionId: string,
): Promise<ConversationSession> {
  const { data } = await api.post<{ data: ConversationSession }>(
    `/conversations/${sessionId}/complete`,
  );
  return data.data;
}
