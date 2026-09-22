import fs from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [inputPath, checkpointPath, outputPath] = process.argv.slice(2);
if (!inputPath || !checkpointPath || !outputPath) {
  throw new Error("Usage: node write_scopus_classifications.mjs INPUT.xlsx CHECKPOINT.json OUTPUT.xlsx");
}

// category_id values were checked against the seven paper_categories rows in
// the user's phpMyAdmin screenshot. Change this map if the target DB differs.
const categoryIds = {
  THEORETICAL_CS: 1,
  AI_ALGORITHMS: 2,
  APPLIED_AI: 3,
  NETWORKS_SECURITY_DISTRIBUTED: 4,
  QUANTUM_INFORMATION: 5,
  COMPUTER_ENGINEERING_IOT_EMBEDDED: 6,
  EDTECH_LEARNING_DIGITAL_LIBRARY: 7,
};

const report = JSON.parse(await fs.readFile(checkpointPath, "utf8"));
const sourceHash = createHash("sha256").update(await fs.readFile(inputPath)).digest("hex");
if (report.source_sha256 !== sourceHash) {
  throw new Error("Checkpoint does not match the source workbook");
}
const results = Object.values(report.results);
if (results.length !== report.total_records || results.length !== 163) {
  throw new Error(`Expected all 163 rows; got ${results.length}`);
}

const matrix = Array.from({ length: 163 }, () => [null, null]);
for (const result of results) {
  const offset = result.row - 2;
  if (!Number.isInteger(offset) || offset < 0 || offset >= matrix.length || matrix[offset][1] !== null) {
    throw new Error(`Invalid or duplicate worksheet row: ${result.row}`);
  }
  const categoryId = result.category_code === null ? null : categoryIds[result.category_code];
  if (result.category_code !== null && !categoryId) {
    throw new Error(`Unknown category: ${result.category_code}`);
  }
  if ((result.confidence === "Preface") !== (categoryId === null)) {
    throw new Error(`Category/confidence mismatch at row ${result.row}`);
  }
  matrix[offset] = [categoryId, result.confidence];
}
if (matrix.some(([, confidence]) => confidence === null)) {
  throw new Error("Checkpoint has missing worksheet rows");
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItem("Documents");
sheet.getRange("AK2:AL164").values = matrix;
workbook.recalculate();
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
const preview = await workbook.render({ sheetName: "Documents", range: "AJ1:AL12", scale: 1.5 });
await fs.writeFile(outputPath.replace(/\.xlsx$/i, "-preview.png"), new Uint8Array(await preview.arrayBuffer()));
console.log(`Wrote ${results.length} classifications to ${outputPath}`);
