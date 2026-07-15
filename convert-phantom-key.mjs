import fs from "node:fs";
import bs58 from "bs58";
import { Keypair } from "@solana/web3.js";

const privateKeyBase58 = fs.readFileSync("solana_wallet_private_key.txt", "utf8").trim();
const secretKey = bs58.decode(privateKeyBase58);
const keypair = Keypair.fromSecretKey(secretKey);

fs.writeFileSync("devnet-keypair.json", JSON.stringify(Array.from(keypair.secretKey)));
console.log("Public key:", keypair.publicKey.toBase58());
console.log("Wrote devnet-keypair.json");