/**
 * Defensive age/consent metadata gate for future external media integrations.
 * This is not a computer-vision safety classifier.
 */
export function validateAdultMediaMetadata({
  rating = "SFW",
  viewerOver18 = false,
  cast = [],
} = {}) {
  if (!["SFW", "M17", "18+"].includes(rating)) {
    throw new Error("Unknown content rating");
  }
  if (rating !== "18+") return true;
  if (!viewerOver18) throw new Error("18+ content requires adult verification");
  if (!Array.isArray(cast) || cast.length < 1) {
    throw new Error("18+ content requires identified participants");
  }
  for (const person of cast) {
    if (!Number.isInteger(person.age) || person.age < 18) {
      throw new Error("Underage or age-unknown participant is forbidden");
    }
    if (person.isRealPerson && person.explicitConsent !== true) {
      throw new Error("Real-person sexual content requires verified consent");
    }
  }
  return true;
}
