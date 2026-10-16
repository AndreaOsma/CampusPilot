import assert from "node:assert/strict";
import { test } from "node:test";
import { isAllowed, isForwardingVerification, toItem } from "../src/index.js";

test("solo admite el dominio del buzón universitario", () => {
  assert.equal(isAllowed("estudiante+caf_=bandeja=example.com@uoc.edu", "uoc.edu"), true);
  assert.equal(isAllowed("x@campus.uoc.edu", "uoc.edu"), true);
  assert.equal(isAllowed("spam@evil-uoc.edu", "uoc.edu"), false);
  assert.equal(isAllowed("spam@example.com", "uoc.edu"), false);
  assert.equal(isAllowed("x@uoc.edu", ""), false);
});

test("reconoce la verificación del reenvío de Gmail", () => {
  assert.equal(isForwardingVerification("forwarding-noreply@google.com"), true);
  assert.equal(isForwardingVerification("aula@uoc.edu"), false);
});

test("convierte el correo al formato de Campus Pilot", () => {
  const item = toItem(
    { messageId: "<a@b>", from: { name: "Aula", address: "aula@uoc.edu" }, subject: "Vídeo R1", date: "2026-10-05T07:30:00.000Z", text: "Hola", html: "<p>Hola</p>" },
    { from: "x@uoc.edu", to: "bandeja@example.com", messageId: null }
  );
  assert.deepEqual(item, {
    message_id: "<a@b>",
    sender: "Aula <aula@uoc.edu>",
    recipient: "bandeja@example.com",
    subject: "Vídeo R1",
    date: "2026-10-05T07:30:00.000Z",
    text: "Hola",
    html: undefined,
  });
  const htmlOnly = toItem({ html: "<p>Solo HTML</p>" }, { from: "x@uoc.edu", to: "t", messageId: "<h@b>" });
  assert.equal(htmlOnly.message_id, "<h@b>");
  assert.equal(htmlOnly.html, "<p>Solo HTML</p>");
});
