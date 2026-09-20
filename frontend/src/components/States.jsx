import React from "react";
import { DueoCharacter } from "./DueoCharacter";

export function EmptyState({ line = "Nothing for you to do.", testid = "empty-state" }) {
  return (
    <div data-testid={testid} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20, padding: "56px 20px", textAlign: "center" }}>
      <DueoCharacter shape="cloud" mood="sleepy" tone="butter" size={140} />
      <div style={{ fontSize: 18, color: "#57524A" }}>{line}</div>
    </div>
  );
}

export function ErrorState({ onRetry, refId, message = "Something went wrong." }) {
  return (
    <div data-testid="error-state" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "48px 20px", textAlign: "center" }}>
      <DueoCharacter shape="burst" mood="alert" tone="coral" size={130} bob={false} />
      <div style={{ fontSize: 18 }}>{message}</div>
      {onRetry && (
        <button className="pill pill-k sm" onClick={onRetry} data-testid="error-retry">Try again</button>
      )}
      {refId && <div className="mono" style={{ fontSize: 12, color: "#57524A" }}>Reference {refId}</div>}
    </div>
  );
}

export default EmptyState;
