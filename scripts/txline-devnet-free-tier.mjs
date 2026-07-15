#!/usr/bin/env node
/*
  TxLINE devnet free-tier subscription and API activation script.

  Install runtime dependencies first:
    npm install @solana/web3.js @solana/spl-token tweetnacl

  Example:
    node scripts/txline-devnet-free-tier.mjs --confirm-devnet

  Required wallet:
    Uses --keypair, SOLANA_KEYPAIR_PATH, or ~/.config/solana/id.json.

  Notes:
    - TxLINE documents devnet free tier service level 1.
    - Service level 12 is documented for mainnet real-time access, not devnet.
    - Free tier requires no TxL payment.
    - Creating the Token-2022 associated token account may require devnet SOL rent.
*/

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

import {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  sendAndConfirmTransaction,
} from "@solana/web3.js";
import {
  ASSOCIATED_TOKEN_PROGRAM_ID,
  TOKEN_2022_PROGRAM_ID,
  createAssociatedTokenAccountInstruction,
  getAssociatedTokenAddressSync,
} from "@solana/spl-token";
import nacl from "tweetnacl";

const DEVNET = {
  rpcUrl: "https://api.devnet.solana.com",
  apiOrigin: "https://txline-dev.txodds.com",
  programId: new PublicKey("6pW64gN1s2uqjHkn1unFeEjAwJkPGHoppGvS715wyP2J"),
  txlTokenMint: new PublicKey("4Zao8ocPhmMgq7PdsYWyxvqySMGx7xb9cMftPMkEokRG"),
};

const SERVICE_LEVELS = new Map([
  [1, "World Cup & Int Friendlies with 60-second delay"],
]);
const UNDOCUMENTED_DEVNET_SERVICE_LEVELS = new Set([12]);

const SUBSCRIBE_DISCRIMINATOR = Buffer.from([254, 28, 191, 138, 156, 179, 183, 53]);
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ENV_PATH = path.resolve(SCRIPT_DIR, "../backend/.env");

main().catch((error) => {
  console.error(`\nERROR: ${error.message}`);
  process.exitCode = 1;
});

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  const serviceLevelId = resolveServiceLevel(args);
  const durationWeeks = Number(args.weeks ?? 4);
  const selectedLeagues = parseSelectedLeagues(args.leagues);
  const keypairPath = expandHome(args.keypair ?? process.env.SOLANA_KEYPAIR_PATH ?? defaultKeypairPath());
  const envPath = path.resolve(args.env ?? DEFAULT_ENV_PATH);
  const rpcUrl = String(args.rpcUrl ?? DEVNET.rpcUrl);
  const shouldWriteEnv = !args.noEnvWrite;
  const shouldCreateTokenAccount = !args.skipAtaCreate;

  validateDurationWeeks(durationWeeks);
  await confirmDevnet(args);

  const wallet = loadKeypair(keypairPath);
  const connection = new Connection(rpcUrl, "confirmed");

  console.log("TxLINE devnet free-tier activation");
  console.log(`Wallet: ${wallet.publicKey.toBase58()}`);
  console.log(`Service level: ${serviceLevelId} (${serviceLevelDescription(serviceLevelId)})`);
  console.log(`Duration: ${durationWeeks} weeks`);
  console.log(`Selected leagues: ${selectedLeagues.length ? selectedLeagues.join(",") : "(standard bundle)"}`);
  console.log(`RPC: ${rpcUrl}`);
  console.log(`API: ${DEVNET.apiOrigin}`);

  const balanceLamports = await connection.getBalance(wallet.publicKey, "confirmed");
  if (balanceLamports <= 0) {
    throw new Error("Wallet has no devnet SOL. Fund it with `solana airdrop 1 --url devnet`.");
  }

  const txSig =
    args.txSig ??
    (await subscribeFreeTier({
      connection,
      wallet,
      serviceLevelId,
      durationWeeks,
      createTokenAccount: shouldCreateTokenAccount,
    }));

  console.log(`Subscription transaction: ${txSig}`);

  const guestJwt = await startGuestSession(DEVNET.apiOrigin);
  console.log(`Guest JWT: ${maskSecret(guestJwt)}`);

  const apiToken = await activateApiToken({
    apiOrigin: DEVNET.apiOrigin,
    guestJwt,
    txSig,
    wallet,
    selectedLeagues,
  });
  console.log(`API token: ${maskSecret(apiToken)}`);

  if (shouldWriteEnv) {
    writeBackendEnv(envPath, {
      TXLINE_BASE_URL: DEVNET.apiOrigin,
      TXLINE_GUEST_JWT: guestJwt,
      TXLINE_API_TOKEN: apiToken,
      TXLINE_FIXTURES_SNAPSHOT_PATH: "/api/fixtures/snapshot",
      TXLINE_ODDS_SNAPSHOT_PATH: "/api/odds/snapshot/<fixture_id>",
      TXLINE_SCORES_SNAPSHOT_PATH: "/api/scores/snapshot/<fixture_id>",
      TXLINE_ODDS_STREAM_PATH: "/api/odds/stream",
      TXLINE_SCORES_STREAM_PATH: "/api/scores/stream",
    });
    console.log(`Updated env file: ${envPath}`);
  }

  console.log("\nDone. You can now run:");
  console.log("  cd backend");
  console.log("  .venv\\Scripts\\python -m app.cli txline-probe");
}

async function subscribeFreeTier({
  connection,
  wallet,
  serviceLevelId,
  durationWeeks,
  createTokenAccount,
}) {
  const [tokenTreasuryPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("token_treasury_v2")],
    DEVNET.programId,
  );
  const [pricingMatrixPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("pricing_matrix")],
    DEVNET.programId,
  );
  const tokenTreasuryVault = getAssociatedTokenAddressSync(
    DEVNET.txlTokenMint,
    tokenTreasuryPda,
    true,
    TOKEN_2022_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
  );
  const userTokenAccount = getAssociatedTokenAddressSync(
    DEVNET.txlTokenMint,
    wallet.publicKey,
    false,
    TOKEN_2022_PROGRAM_ID,
    ASSOCIATED_TOKEN_PROGRAM_ID,
  );

  const transaction = new Transaction();
  const userTokenAccountInfo = await connection.getAccountInfo(userTokenAccount, "confirmed");
  if (!userTokenAccountInfo) {
    if (!createTokenAccount) {
      throw new Error(
        `Missing TxL token account ${userTokenAccount.toBase58()}. ` +
          "Rerun without --skip-ata-create or create it manually first.",
      );
    }
    transaction.add(
      createAssociatedTokenAccountInstruction(
        wallet.publicKey,
        userTokenAccount,
        wallet.publicKey,
        DEVNET.txlTokenMint,
        TOKEN_2022_PROGRAM_ID,
        ASSOCIATED_TOKEN_PROGRAM_ID,
      ),
    );
  }

  transaction.add(
    new TransactionInstruction({
      programId: DEVNET.programId,
      keys: [
        { pubkey: wallet.publicKey, isSigner: true, isWritable: true },
        { pubkey: pricingMatrixPda, isSigner: false, isWritable: false },
        { pubkey: DEVNET.txlTokenMint, isSigner: false, isWritable: false },
        { pubkey: userTokenAccount, isSigner: false, isWritable: true },
        { pubkey: tokenTreasuryVault, isSigner: false, isWritable: true },
        { pubkey: tokenTreasuryPda, isSigner: false, isWritable: false },
        { pubkey: TOKEN_2022_PROGRAM_ID, isSigner: false, isWritable: false },
        { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
        { pubkey: ASSOCIATED_TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      ],
      data: subscribeInstructionData(serviceLevelId, durationWeeks),
    }),
  );

  console.log("Sending devnet subscribe transaction...");
  return sendAndConfirmTransaction(connection, transaction, [wallet], {
    commitment: "confirmed",
  });
}

function subscribeInstructionData(serviceLevelId, durationWeeks) {
  const data = Buffer.alloc(SUBSCRIBE_DISCRIMINATOR.length + 3);
  SUBSCRIBE_DISCRIMINATOR.copy(data, 0);
  data.writeUInt16LE(serviceLevelId, SUBSCRIBE_DISCRIMINATOR.length);
  data.writeUInt8(durationWeeks, SUBSCRIBE_DISCRIMINATOR.length + 2);
  return data;
}

async function startGuestSession(apiOrigin) {
  const payload = await postJson(`${apiOrigin}/auth/guest/start`);
  const token = typeof payload === "string" ? payload : payload?.token;
  if (!token || typeof token !== "string") {
    throw new Error("Guest session response did not include a token.");
  }
  return token;
}

async function activateApiToken({ apiOrigin, guestJwt, txSig, wallet, selectedLeagues }) {
  const messageString = `${txSig}:${selectedLeagues.join(",")}:${guestJwt}`;
  const message = new TextEncoder().encode(messageString);
  const signatureBytes = nacl.sign.detached(message, wallet.secretKey);
  const walletSignature = Buffer.from(signatureBytes).toString("base64");

  const payload = await postJson(
    `${apiOrigin}/api/token/activate`,
    {
      txSig,
      walletSignature,
      leagues: selectedLeagues,
    },
    {
      Authorization: `Bearer ${guestJwt}`,
    },
  );

  const token = typeof payload === "string" ? payload : payload?.token;
  if (!token || typeof token !== "string") {
    throw new Error("Activation response did not include an API token.");
  }
  return token;
}

async function postJson(url, body = undefined, headers = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...headers,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${url} returned HTTP ${response.status}: ${text}`);
  }
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function resolveServiceLevel(args) {
  if (args.serviceLevel !== undefined) {
    const value = Number(args.serviceLevel);
    validateServiceLevel(value, args);
    return value;
  }
  return 1;
}

async function confirmDevnet(args) {
  if (args.confirmDevnet || args.txSig) {
    return;
  }
  if (!process.stdin.isTTY) {
    throw new Error("Pass --confirm-devnet to send the devnet subscription transaction.");
  }

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = await rl.question(
      "This will send a Solana DEVNET transaction. Type DEVNET to continue: ",
    );
    if (answer.trim() !== "DEVNET") {
      throw new Error("Devnet confirmation was not provided.");
    }
  } finally {
    rl.close();
  }
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${arg}`);
    }
    const [rawKey, inlineValue] = arg.slice(2).split("=", 2);
    const key = toCamelCase(rawKey);
    if (
      [
        "help",
        "confirmDevnet",
        "allowUndocumentedServiceLevel",
        "noEnvWrite",
        "skipAtaCreate",
      ].includes(key)
    ) {
      args[key] = true;
      continue;
    }
    const value = inlineValue ?? argv[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`Missing value for --${rawKey}`);
    }
    args[key] = value;
    if (inlineValue === undefined) {
      index += 1;
    }
  }
  return args;
}

function toCamelCase(value) {
  return value.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

function validateServiceLevel(value, args) {
  if (SERVICE_LEVELS.has(value)) {
    return;
  }
  if (UNDOCUMENTED_DEVNET_SERVICE_LEVELS.has(value)) {
    if (args.allowUndocumentedServiceLevel) {
      return;
    }
    throw new Error(
      "Service level 12 is documented for mainnet, not devnet. " +
        "Pass --allow-undocumented-service-level only after checking the devnet pricing matrix.",
    );
  }
  throw new Error("Devnet World Cup free tier service level must be 1.");
}

function serviceLevelDescription(value) {
  return SERVICE_LEVELS.get(value) ?? "undocumented devnet service level";
}

function validateDurationWeeks(value) {
  if (!Number.isInteger(value) || value <= 0 || value % 4 !== 0) {
    throw new Error("--weeks must be a positive multiple of 4.");
  }
  if (value > 52) {
    throw new Error("--weeks must be 52 or less.");
  }
}

function parseSelectedLeagues(value) {
  if (!value) {
    return [];
  }
  return String(value)
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item));
}

function defaultKeypairPath() {
  return path.join(os.homedir(), ".config", "solana", "id.json");
}

function expandHome(value) {
  const text = String(value);
  if (text === "~") {
    return os.homedir();
  }
  if (text.startsWith("~/") || text.startsWith("~\\")) {
    return path.join(os.homedir(), text.slice(2));
  }
  return text;
}

function loadKeypair(keypairPath) {
  if (!fs.existsSync(keypairPath)) {
    throw new Error(`Keypair file not found: ${keypairPath}`);
  }
  const parsed = JSON.parse(fs.readFileSync(keypairPath, "utf8"));
  const secretKey = Array.isArray(parsed) ? parsed : parsed.secretKey;
  if (!Array.isArray(secretKey)) {
    throw new Error("Keypair file must be a Solana CLI JSON array or contain secretKey.");
  }
  return Keypair.fromSecretKey(Uint8Array.from(secretKey));
}

function writeBackendEnv(envPath, updates) {
  const existing = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : "";
  const lines = existing.split(/\r?\n/);
  const seen = new Set();
  const updatedLines = lines.map((line) => {
    const match = line.match(/^([A-Z0-9_]+)=/);
    if (!match || !(match[1] in updates)) {
      return line;
    }
    seen.add(match[1]);
    return `${match[1]}=${updates[match[1]]}`;
  });

  for (const [key, value] of Object.entries(updates)) {
    if (!seen.has(key)) {
      updatedLines.push(`${key}=${value}`);
    }
  }

  fs.mkdirSync(path.dirname(envPath), { recursive: true });
  fs.writeFileSync(envPath, `${updatedLines.join("\n").replace(/\n+$/, "")}\n`, "utf8");
}

function maskSecret(value) {
  if (!value || value.length <= 16) {
    return "(set)";
  }
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function printHelp() {
  console.log(`
Usage:
  node scripts/txline-devnet-free-tier.mjs --confirm-devnet

Options:
  --service-level 1          Devnet free tier to subscribe to. Defaults to 1.
  --weeks 4                  Subscription duration. Must be a multiple of 4.
  --keypair <path>           Solana keypair JSON path.
  --rpc-url <url>            Devnet RPC URL override.
  --leagues <csv>            Selected league IDs. Default is standard bundle.
  --env <path>               Env file to update. Default: backend/.env.
  --no-env-write             Print tokens only; do not update backend/.env.
  --skip-ata-create          Do not create missing TxL associated token account.
  --tx-sig <signature>       Activate an existing subscribe transaction.
  --confirm-devnet           Skip the interactive DEVNET confirmation prompt.
  --allow-undocumented-service-level
                             Permit service level 12 after manual devnet matrix check.
  --help                     Show this help.
`);
}
