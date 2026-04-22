"""
Banking Query Service
Intent-aware grounded analytics and reasoning over banking datasets.
"""

from __future__ import annotations

import glob
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.date_utils import DateUtils

logger = get_logger(__name__)


@dataclass
class DatasetBundle:
    name: str
    dataframe: pd.DataFrame
    source_files: List[str]


class BankingQueryService:
    """Grounded banking analytics, retrieval, and reasoning over structured data."""

    ACTION_KEYWORDS = {
        "notification": ["email", "sms", "notify", "notification", "message", "slack"],
        "scheduling": ["schedule", "appointment", "meeting", "book", "calendar", "reschedule"],
        "loan": ["loan", "mortgage", "apr", "refinance", "emi", "interest rate"],
        "compliance": ["kyc", "aml", "audit", "fraud", "regulation", "policy", "sar", "ctr"],
    }

    def __init__(self):
        self._datasets: Optional[Dict[str, DatasetBundle]] = None

    def classify_intent(self, query: str) -> Dict[str, Any]:
        """Classify the query into intent and route."""
        query_lower = query.lower()

        for route, keywords in self.ACTION_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                return {
                    "intent": "action_based",
                    "route": f"{route}_agent" if route != "notification" and route != "scheduling" else f"{route}_agent",
                }

        analytical_markers = [
            "total", "sum", "average", "avg", "count", "how many",
            "trend", "group by", "per ", "highest", "lowest", "top", "spend",
        ]
        if any(marker in query_lower for marker in analytical_markers):
            return {"intent": "analytical", "route": "banking_data_agent"}

        if any(word in query_lower for word in ["why", "how", "explain", "reason", "balance change", "before", "after"]):
            return {"intent": "reasoning", "route": "banking_data_agent"}

        if any(word in query_lower for word in ["maintenance", "outage", "downtime", "system issue", "service issue", "incident", "status"]):
            return {"intent": "operational", "route": "banking_data_agent"}

        return {"intent": "informational", "route": "banking_data_agent"}

    def answer_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Answer a banking question using only current structured datasets."""
        datasets = self._load_datasets()
        intent_info = self.classify_intent(query)
        intent = intent_info["intent"]

        if intent == "informational":
            result = self._handle_informational(query, datasets)
        elif intent == "analytical":
            result = self._handle_analytical(query, datasets)
        elif intent == "reasoning":
            result = self._handle_reasoning(query, datasets)
        elif intent == "operational":
            result = self._handle_operational(query, datasets)
        else:
            result = self._not_available("This information is not available in the current dataset")

        result.setdefault("intent", intent)
        result.setdefault("grounded", result.get("success", False))
        result.setdefault("sources", self._collect_sources(result, datasets))
        return result

    def _load_datasets(self) -> Dict[str, DatasetBundle]:
        """Load structured datasets from upload and data directories."""
        if self._datasets is not None:
            return self._datasets

        bundles: Dict[str, List[Tuple[pd.DataFrame, str]]] = {}
        paths = (
            glob.glob(os.path.join(settings.upload_dir, "raw", "*.csv"))
            + glob.glob(os.path.join(settings.upload_dir, "raw", "*.xml"))
            + glob.glob("data/*.csv")
            + glob.glob("data/*.xml")
        )

        for path in paths:
            try:
                dataset_name = self._infer_dataset_name(path)
                if dataset_name is None:
                    continue

                if path.lower().endswith(".csv"):
                    frame = pd.read_csv(path)
                else:
                    frame = self._read_xml_to_dataframe(path)

                if frame is None or frame.empty:
                    continue

                frame = self._normalize_dataframe(frame)
                bundles.setdefault(dataset_name, []).append((frame, os.path.basename(path)))
            except Exception as exc:
                logger.warning("Skipping dataset file", file_path=path, error=str(exc))

        resolved: Dict[str, DatasetBundle] = {}
        for name, entries in bundles.items():
            merged = pd.concat([df for df, _ in entries], ignore_index=True, sort=False)
            sources = [source for _, source in entries]
            resolved[name] = DatasetBundle(name=name, dataframe=merged, source_files=sources)

        self._datasets = resolved
        return resolved

    def _infer_dataset_name(self, path: str) -> Optional[str]:
        filename = os.path.basename(path).lower()
        if "transaction_processing" in filename or "processing" in filename:
            return "transaction_processing"
        if "maintenance" in filename:
            return "bank_maintenance"
        if "customer" in filename:
            return "customers"
        if "transaction" in filename:
            return "transactions"
        return None

    def _read_xml_to_dataframe(self, path: str) -> pd.DataFrame:
        tree = ET.parse(path)
        root = tree.getroot()
        records = self._extract_xml_records(root)
        if not records:
            flattened = self._flatten_xml_tree(root)
            return pd.DataFrame(flattened) if flattened else pd.DataFrame()
        return pd.DataFrame(records)

    def _extract_xml_records(self, root: ET.Element) -> List[Dict[str, Any]]:
        candidate_parent = None
        candidate_tag = None
        candidate_count = 0

        for parent in root.iter():
            counts: Dict[str, int] = {}
            for child in list(parent):
                counts[child.tag] = counts.get(child.tag, 0) + 1
            for tag, count in counts.items():
                if count > candidate_count and count > 1:
                    candidate_parent = parent
                    candidate_tag = tag
                    candidate_count = count

        if candidate_parent is None or candidate_tag is None:
            return []

        records: List[Dict[str, Any]] = []
        for child in list(candidate_parent):
            if child.tag != candidate_tag:
                continue
            row: Dict[str, Any] = {}
            row.update({f"attr_{k}": v for k, v in child.attrib.items()})
            row.update(self._flatten_xml_element(child))
            if row:
                records.append(row)
        return records

    def _flatten_xml_element(self, element: ET.Element, prefix: str = "") -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for child in list(element):
            key = f"{prefix}_{child.tag}" if prefix else child.tag
            if list(child):
                data.update(self._flatten_xml_element(child, key))
            else:
                text = (child.text or "").strip()
                if text:
                    data[key] = text
                for attr_key, attr_val in child.attrib.items():
                    data[f"{key}_{attr_key}"] = attr_val
        return data

    def _flatten_xml_tree(self, root: ET.Element) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for element in root.iter():
            text = (element.text or "").strip()
            if text:
                rows.append({"tag": element.tag, "value": text})
        return rows

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        normalized.columns = [self._normalize_column_name(col) for col in normalized.columns]
        for col in normalized.columns:
            if normalized[col].dtype == object:
                numeric = pd.to_numeric(normalized[col], errors="coerce")
                if numeric.notna().sum() > 0 and numeric.notna().sum() >= max(1, int(len(normalized) * 0.5)):
                    normalized[col] = numeric
                    continue
                if any(token in col for token in ["date", "time", "created", "updated", "posted"]):
                    converted = pd.to_datetime(normalized[col], errors="coerce")
                    if converted.notna().sum() > 0 and converted.notna().sum() >= max(1, int(len(normalized) * 0.5)):
                        normalized[col] = converted
        return normalized

    def _normalize_column_name(self, value: Any) -> str:
        text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower())
        return re.sub(r"_+", "_", text).strip("_")

    def _handle_informational(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        query_lower = query.lower()
        if "transaction" in query_lower or "payment" in query_lower or "debit" in query_lower or "credit" in query_lower:
            transaction_result = self._lookup_transactions(query, datasets)
            if transaction_result["success"]:
                return transaction_result

        if "balance" in query_lower or "customer" in query_lower or "account" in query_lower:
            customer_result = self._lookup_customer(query, datasets)
            if customer_result["success"]:
                return customer_result

        return self._not_available("This information is not available in the current dataset")

    def _handle_analytical(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        transactions = datasets.get("transactions")
        if transactions is None:
            return self._not_available("This information is not available in the current dataset")

        df = self._filter_transactions(transactions.dataframe, query)
        if df.empty:
            return self._not_available("This information is not available in the current dataset")

        if self._is_transaction_list_query(query):
            return self._build_ranked_transaction_list(df, query, transactions.source_files)

        operation = self._detect_aggregation_operation(query)
        amount_col = self._find_column(df, ["amount", "transaction_amount", "value"])
        group_col = None

        if any(term in query.lower() for term in ["category", "group by", "by category", "spend by"]):
            group_col = self._find_column(df, ["category", "txn_type", "transaction_type", "type", "merchant", "description"])

        if operation == "count":
            if group_col:
                grouped = df.groupby(group_col).size().reset_index(name="count")
                return {
                    "success": True,
                    "data": grouped.to_dict(orient="records"),
                    "summary": f"Counted {int(len(df))} matching transactions grouped by {group_col}.",
                    "explanation": self._build_filter_explanation(df, query),
                    "sources": transactions.source_files,
                }
            return {
                "success": True,
                "result": int(len(df)),
                "explanation": self._build_filter_explanation(df, query),
                "sources": transactions.source_files,
            }

        if amount_col is None:
            return self._not_available("This information is not available in the current dataset")

        if group_col:
            agg_name = "sum" if operation == "sum" else "mean" if operation in {"avg", "average"} else operation
            grouped = df.groupby(group_col)[amount_col].agg(agg_name).reset_index()
            grouped.rename(columns={amount_col: operation}, inplace=True)
            return {
                "success": True,
                "data": grouped.to_dict(orient="records"),
                "summary": f"Calculated {operation} of {amount_col} grouped by {group_col}.",
                "explanation": self._build_filter_explanation(df, query),
                "sources": transactions.source_files,
            }

        numeric_series = pd.to_numeric(df[amount_col], errors="coerce").dropna()
        if numeric_series.empty:
            return self._not_available("This information is not available in the current dataset")

        if operation == "sum":
            value = float(numeric_series.sum())
        elif operation in {"avg", "average"}:
            value = float(numeric_series.mean())
        elif operation == "min":
            value = float(numeric_series.min())
        elif operation == "max":
            value = float(numeric_series.max())
        else:
            value = float(numeric_series.sum())

        return {
            "success": True,
            "result": round(value, 2),
            "explanation": self._build_filter_explanation(df, query, amount_col=amount_col, operation=operation),
            "sources": transactions.source_files,
        }

    def _is_transaction_list_query(self, query: str) -> bool:
        query_lower = query.lower()
        list_markers = ["list", "show", "top", "highest", "lowest", "largest", "smallest"]
        return "transaction" in query_lower and any(marker in query_lower for marker in list_markers)

    def _build_ranked_transaction_list(
        self,
        df: pd.DataFrame,
        query: str,
        source_files: List[str],
    ) -> Dict[str, Any]:
        amount_col = self._find_column(df, ["amount", "transaction_amount", "value"])
        date_col = self._find_column(df, ["date", "transaction_date", "posted_date", "created_at"])
        limit = self._extract_limit(query) or 10
        query_lower = query.lower()

        sort_col = amount_col or date_col
        if sort_col:
            ascending = any(term in query_lower for term in ["lowest", "smallest"])
            if amount_col and any(term in query_lower for term in ["top", "highest", "largest", "lowest", "smallest"]):
                sort_series = pd.to_numeric(df[sort_col], errors="coerce").abs()
                df = df.assign(_sort_metric=sort_series).sort_values("_sort_metric", ascending=ascending, na_position="last")
                df = df.drop(columns=["_sort_metric"])
            elif date_col and any(term in query_lower for term in ["latest", "recent", "newest"]):
                df = df.sort_values(date_col, ascending=False, na_position="last")
            elif date_col:
                df = df.sort_values(date_col, ascending=False, na_position="last")

        preview = df.head(limit).copy()
        for col in preview.columns:
            if pd.api.types.is_datetime64_any_dtype(preview[col]):
                preview[col] = preview[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "success": True,
            "data": preview.fillna("").to_dict(orient="records"),
            "summary": f"Returned the top {min(limit, len(preview))} transaction records from {len(df)} matches.",
            "explanation": self._build_list_explanation(df, query, amount_col=amount_col, limit=limit),
            "sources": source_files,
        }

    def _handle_reasoning(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        transactions = datasets.get("transactions")
        processing = datasets.get("transaction_processing")
        customers = datasets.get("customers")

        reasoning_parts: List[str] = []
        source_files: List[str] = []

        if processing is not None:
            source_files.extend(processing.source_files)
            related_rules = self._filter_generic(processing.dataframe, query)
            if not related_rules.empty:
                preview = related_rules.head(3).fillna("").astype(str).to_dict(orient="records")
                reasoning_parts.append(f"Processing rules matched: {preview}")

        if transactions is not None:
            source_files.extend(transactions.source_files)
            tx_df = self._filter_transactions(transactions.dataframe, query)
            if not tx_df.empty:
                tx_row = tx_df.iloc[0]
                signed_amount = self._resolve_signed_amount(tx_row)
                txn_type = self._extract_txn_type_from_row(tx_row)
                reasoning_parts.append(
                    f"Matched transaction {self._safe_lookup(tx_row, ['transaction_id', 'txn_id', 'id']) or 'record'} "
                    f"with type {txn_type or 'unknown'} and amount {signed_amount}."
                )

                if customers is not None:
                    source_files.extend(customers.source_files)
                    customer_df = self._match_customer_dataframe(customers.dataframe, query)
                    balance_col = self._find_column(customers.dataframe, ["balance", "current_balance", "account_balance", "available_balance"])
                    if not customer_df.empty and balance_col:
                        current_balance = pd.to_numeric(customer_df.iloc[0][balance_col], errors="coerce")
                        if pd.notna(current_balance):
                            before_balance = float(current_balance - signed_amount)
                            reasoning_parts.append(
                                f"Using current balance {round(float(current_balance), 2)}, "
                                f"the estimated balance before this transaction was {round(before_balance, 2)} "
                                f"and after the transaction it is {round(float(current_balance), 2)}."
                            )

        if not reasoning_parts:
            return self._not_available("This information is not available in the current dataset")

        return {
            "success": True,
            "result": "Balance reasoning completed",
            "explanation": " ".join(reasoning_parts),
            "sources": sorted(set(source_files)),
        }

    def _handle_operational(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        maintenance = datasets.get("bank_maintenance")
        if maintenance is None:
            return self._not_available("This information is not available in the current dataset")

        df = self._filter_generic(maintenance.dataframe, query)
        if df.empty:
            df = maintenance.dataframe
        if df.empty:
            return self._not_available("This information is not available in the current dataset")

        row = df.iloc[0]
        status = self._safe_lookup(row, ["status", "incident_status", "state"]) or "unknown"
        impact = self._safe_lookup(row, ["impact", "severity", "effect", "description"]) or "No impact details available"
        service = self._safe_lookup(row, ["service", "system", "module", "component"]) or "banking system"

        return {
            "success": True,
            "status": str(status),
            "impact": str(impact),
            "message": f"{service} status is {status}. {impact}",
            "sources": maintenance.source_files,
        }

    def _lookup_customer(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        customers = datasets.get("customers")
        if customers is None:
            return self._not_available("This information is not available in the current dataset")

        matched = self._match_customer_dataframe(customers.dataframe, query)
        if matched.empty:
            return self._not_available("This information is not available in the current dataset")

        row = matched.iloc[0]
        balance_col = self._find_column(matched, ["balance", "current_balance", "account_balance", "available_balance"])
        account_col = self._find_column(matched, ["account_id", "account_number", "customer_id", "id", "uuid"])
        name_parts = [
            str(row[col]) for col in matched.columns
            if col in {"first_name", "last_name", "full_name", "customer_name"} and pd.notna(row[col])
        ]
        payload: Dict[str, Any] = {
            "success": True,
            "data": {
                "customer": " ".join(name_parts).strip() or "Matched customer",
                "identifier": str(row[account_col]) if account_col and pd.notna(row[account_col]) else None,
            },
            "summary": "Customer record retrieved from the current dataset.",
            "sources": customers.source_files,
        }
        if balance_col and pd.notna(row[balance_col]):
            payload["result"] = round(float(pd.to_numeric(row[balance_col], errors="coerce")), 2)
            payload["explanation"] = f"Returned the current value from column '{balance_col}' in the customers dataset."
        else:
            payload["explanation"] = "Matched the customer record, but no balance column was available in the current dataset."
        return payload

    def _lookup_transactions(self, query: str, datasets: Dict[str, DatasetBundle]) -> Dict[str, Any]:
        transactions = datasets.get("transactions")
        if transactions is None:
            return self._not_available("This information is not available in the current dataset")

        df = self._filter_transactions(transactions.dataframe, query)
        if df.empty:
            return self._not_available("This information is not available in the current dataset")

        date_col = self._find_column(df, ["date", "transaction_date", "posted_date", "created_at"])
        if date_col:
            df = df.sort_values(by=date_col, ascending=False, na_position="last")

        preview = df.head(5).copy()
        for col in preview.columns:
            if pd.api.types.is_datetime64_any_dtype(preview[col]):
                preview[col] = preview[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        return {
            "success": True,
            "data": preview.fillna("").to_dict(orient="records"),
            "summary": f"Found {len(df)} matching transaction records.",
            "sources": transactions.source_files,
        }

    def _match_customer_dataframe(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        identifiers = self._extract_identifiers(query)
        matched = df.copy()
        candidate_columns = [
            col for col in df.columns
            if any(key in col for key in ["customer", "account", "user", "id", "uuid", "email", "name"])
        ]

        for value in identifiers.values():
            if not value:
                continue
            for col in candidate_columns:
                series = df[col].astype(str).str.lower()
                mask = series == value.lower()
                if mask.any():
                    return df[mask]
                partial = series.str.contains(re.escape(value.lower()), na=False)
                if partial.any():
                    return df[partial]

        quoted = re.findall(r'"([^"]+)"', query)
        if quoted:
            term = quoted[0].lower()
            for col in candidate_columns:
                mask = df[col].astype(str).str.lower().str.contains(re.escape(term), na=False)
                if mask.any():
                    return df[mask]

        return matched.iloc[0:0]

    def _filter_transactions(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        filtered = df.copy()
        identifiers = self._extract_identifiers(query)

        for value in identifiers.values():
            if not value:
                continue
            id_cols = [col for col in filtered.columns if any(key in col for key in ["customer", "account", "user", "transaction", "txn", "id"])]
            matched = False
            for col in id_cols:
                mask = filtered[col].astype(str).str.lower() == value.lower()
                if mask.any():
                    filtered = filtered[mask]
                    matched = True
                    break
            if not matched:
                for col in id_cols:
                    mask = filtered[col].astype(str).str.lower().str.contains(re.escape(value.lower()), na=False)
                    if mask.any():
                        filtered = filtered[mask]
                        break

        type_filter = self._extract_transaction_type(query)
        if type_filter:
            type_cols = [col for col in filtered.columns if any(key in col for key in ["type", "category", "description"])]
            for col in type_cols:
                mask = filtered[col].astype(str).str.lower().str.contains(type_filter, na=False)
                if mask.any():
                    filtered = filtered[mask]
                    break
            amount_col = self._find_column(filtered, ["amount", "transaction_amount", "value"])
            if amount_col and type_filter == "debit":
                numeric = pd.to_numeric(filtered[amount_col], errors="coerce")
                if numeric.notna().any():
                    filtered = filtered[numeric < 0] if (numeric < 0).any() else filtered
            if amount_col and type_filter in {"credit", "deposit"}:
                numeric = pd.to_numeric(filtered[amount_col], errors="coerce")
                if numeric.notna().any():
                    filtered = filtered[numeric > 0] if (numeric > 0).any() else filtered

        start_date, end_date = DateUtils.extract_date_range(query)
        if start_date or end_date:
            date_col = self._find_column(filtered, ["date", "transaction_date", "posted_date", "created_at"])
            if date_col:
                date_series = pd.to_datetime(filtered[date_col], errors="coerce")
                filtered = filtered.assign(_date_filter=date_series)
                if start_date:
                    filtered = filtered[filtered["_date_filter"] >= start_date]
                if end_date:
                    filtered = filtered[filtered["_date_filter"] <= end_date]
                filtered = filtered.drop(columns=["_date_filter"])

        return filtered

    def _filter_generic(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        terms = [term for term in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(term) > 2]
        if not terms:
            return df

        masks = []
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                col_series = df[col].astype(str).str.lower()
                mask = pd.Series(False, index=df.index)
                for term in terms:
                    mask = mask | col_series.str.contains(re.escape(term), na=False)
                masks.append(mask)

        if not masks:
            return df.iloc[0:0]

        combined = masks[0]
        for mask in masks[1:]:
            combined = combined | mask
        return df[combined]

    def _extract_identifiers(self, query: str) -> Dict[str, Optional[str]]:
        patterns = {
            "customer_id": r"(?:customer(?:\s+id)?|cust(?:omer)?)[\s:#-]*([a-z0-9_-]+)",
            "account_id": r"(?:account(?:\s+id| number)?)[\s:#-]*([a-z0-9_-]+)",
            "transaction_id": r"(?:transaction(?:\s+id)?|txn(?:\s+id)?)[\s:#-]*([a-z0-9_-]+)",
            "email": r"([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})",
        }
        query_lower = query.lower()
        values: Dict[str, Optional[str]] = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, query_lower)
            values[key] = match.group(1) if match else None
        return values

    def _extract_transaction_type(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        for value in ["debit", "credit", "deposit", "withdrawal", "transfer", "payment"]:
            if value in query_lower:
                return value
        return None

    def _detect_aggregation_operation(self, query: str) -> str:
        query_lower = query.lower()
        if "count" in query_lower or "how many" in query_lower or "number of" in query_lower:
            return "count"
        if "average" in query_lower or "avg" in query_lower or "mean" in query_lower:
            return "avg"
        if "minimum" in query_lower or re.search(r"\bmin\b", query_lower):
            return "min"
        if "maximum" in query_lower or re.search(r"\bmax\b", query_lower):
            return "max"
        return "sum"

    def _extract_limit(self, query: str) -> Optional[int]:
        query_lower = query.lower()
        patterns = [
            r"\btop\s+(\d+)\b",
            r"\blist\s+(\d+)\b",
            r"\bshow\s+(\d+)\b",
            r"\bfirst\s+(\d+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                return int(match.group(1))
        return None

    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        lowered = {col.lower(): col for col in df.columns}
        for candidate in candidates:
            if candidate in lowered:
                return lowered[candidate]
        for candidate in candidates:
            for col in df.columns:
                if candidate in col.lower():
                    return col
        return None

    def _build_filter_explanation(self, df: pd.DataFrame, query: str, amount_col: Optional[str] = None, operation: Optional[str] = None) -> str:
        parts = [f"Matched {len(df)} records from the transactions dataset"]
        txn_type = self._extract_transaction_type(query)
        if txn_type:
            parts.append(f"filtered by transaction type '{txn_type}'")
        start_date, end_date = DateUtils.extract_date_range(query)
        if start_date or end_date:
            parts.append(f"within date range {DateUtils.format_date_range(start_date, end_date)}")
        if amount_col and operation:
            parts.append(f"then applied {operation} on column '{amount_col}'")
        return ", ".join(parts) + "."

    def _build_list_explanation(self, df: pd.DataFrame, query: str, amount_col: Optional[str], limit: int) -> str:
        parts = [f"Matched {len(df)} records from the transactions dataset"]
        txn_type = self._extract_transaction_type(query)
        if txn_type:
            parts.append(f"filtered by transaction type '{txn_type}'")
        start_date, end_date = DateUtils.extract_date_range(query)
        if start_date or end_date:
            parts.append(f"within date range {DateUtils.format_date_range(start_date, end_date)}")
        if amount_col and any(term in query.lower() for term in ["top", "highest", "largest", "lowest", "smallest"]):
            order = "ascending" if any(term in query.lower() for term in ["lowest", "smallest"]) else "descending"
            parts.append(f"ranked by '{amount_col}' in {order} order")
        parts.append(f"returned up to {limit} records")
        return ", ".join(parts) + "."

    def _resolve_signed_amount(self, row: pd.Series) -> float:
        amount = self._safe_lookup(row, ["amount", "transaction_amount", "value"])
        numeric_amount = pd.to_numeric(amount, errors="coerce")
        if pd.notna(numeric_amount):
            if float(numeric_amount) != 0:
                return float(numeric_amount)

        debit = self._safe_lookup(row, ["debit_amount"])
        credit = self._safe_lookup(row, ["credit_amount"])
        debit_val = pd.to_numeric(debit, errors="coerce")
        credit_val = pd.to_numeric(credit, errors="coerce")
        if pd.notna(debit_val):
            return -float(debit_val)
        if pd.notna(credit_val):
            return float(credit_val)
        return 0.0

    def _extract_txn_type_from_row(self, row: pd.Series) -> Optional[str]:
        for col in ["txn_type", "transaction_type", "type", "category", "description"]:
            if col in row.index and pd.notna(row[col]):
                return str(row[col])
        return None

    def _safe_lookup(self, row: pd.Series, candidates: List[str]) -> Any:
        for key in candidates:
            if key in row.index and pd.notna(row[key]):
                return row[key]
        for key in candidates:
            for col in row.index:
                if key in col:
                    value = row[col]
                    if pd.notna(value):
                        return value
        return None

    def _collect_sources(self, result: Dict[str, Any], datasets: Dict[str, DatasetBundle]) -> List[str]:
        if result.get("sources"):
            return sorted(set(result["sources"]))
        sources: List[str] = []
        for bundle in datasets.values():
            sources.extend(bundle.source_files)
        return sorted(set(sources))

    def _not_available(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "message": message,
            "grounded": False,
            "sources": [],
        }


def format_structured_response(payload: Dict[str, Any]) -> str:
    """Render a structured result as stable JSON text for API clients."""
    return json.dumps(payload, indent=2, default=_json_default)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    return str(value)
