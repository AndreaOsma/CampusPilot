import assert from "node:assert/strict";
import { test } from "node:test";
import { isAllowed, isForwardingVerification, toItem } from "../src/index.js";

test("solo admite el dominio del buzón universitario", () => {
  assert.equal(isAllowed("estudiante+caf_=bandeja=example.com@universidad.example", "universidad.example"), true);
  assert.equal(isAllowed("x@campus.universidad.example", "universidad.example"), true);
  assert.equal(isAllowed("spam@evil-universidad.example", "universidad.example"), false);
  assert.equal(isAllowed("spam@example.com", "universidad.example"), false);
  assert.equal(isAllowed("x@universidad.example", ""), false);
});

test("reconoce la verificación del reenvío de Gmail", () => {
  assert.equal(isForwardingVerification("forwarding-noreply@google.com"), true);
  assert.equal(isForwardingVerification("profesorado@universidad.example"), false);
});

test("convierte el correo al formato de Campus Pilot", () => {
  const item = toItem(
    { messageId: "<a@b>", from: { name: "Aula", address: "profesorado@universidad.example" }, subject: "Vídeo R1", date: "2026-10-05T07:30:00.000Z", text: "Hola", html: "<p>Hola</p>" },
    { from: "x@universidad.example", to: "bandeja@example.com", messageId: null }
  );
  assert.deepEqual(item, {
    message_id: "<a@b>",
    sender: "Aula <profesorado@universidad.example>",
    recipient: "bandeja@example.com",
    subject: "Vídeo R1",
    date: "2026-10-05T07:30:00.000Z",
    text: "Hola",
    html: undefined,
  });
  const htmlOnly = toItem({ html: "<p>Solo HTML</p>" }, { from: "x@universidad.example", to: "t", messageId: "<h@b>" });
  assert.equal(htmlOnly.message_id, "<h@b>");
  assert.equal(htmlOnly.html, "<p>Solo HTML</p>");
});
