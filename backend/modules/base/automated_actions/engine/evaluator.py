"""In-memory condition expression evaluator using the Universal AST Filter specification."""

import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger("sovereign.automated_actions.evaluator")


class ASTConditionEvaluator:
    """Evaluates universal AST filter trees against record dictionaries and state diffs in memory."""

    @classmethod
    def evaluate(
        cls,
        condition_tree: Optional[Dict[str, Any]],
        record_data: Dict[str, Any],
        old_record_data: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate a condition tree against record data. Returns True if matched or if tree is empty."""
        if not condition_tree:
            return True

        # Handle either standard QueryEngine schema (logical_operator / conditions)
        # or intuitive TCA shorthand (logic / filters)
        logic = (
            condition_tree.get("logical_operator")
            or condition_tree.get("logic")
            or "AND"
        ).upper()

        sub_items = (
            condition_tree.get("conditions")
            or condition_tree.get("filters")
            or []
        )

        if not sub_items:
            # Check if this node itself is a single FilterNode
            if "field" in condition_tree and "operator" in condition_tree:
                return cls._evaluate_node(condition_tree, record_data, old_record_data, diff)
            return True

        results = []
        for item in sub_items:
            if isinstance(item, dict):
                if "conditions" in item or "filters" in item:
                    # Recursive sub-group
                    res = cls.evaluate(item, record_data, old_record_data, diff)
                elif "field" in item and "operator" in item:
                    # Leaf node
                    res = cls._evaluate_node(item, record_data, old_record_data, diff)
                else:
                    res = True
                results.append(res)

        if not results:
            return True

        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        elif logic == "NOT":
            return not all(results)
        return True

    @classmethod
    def _evaluate_node(
        cls,
        node: Dict[str, Any],
        record_data: Dict[str, Any],
        old_record_data: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
    ) -> bool:
        field_name = node.get("field", "")
        op = node.get("operator", "eq").lower()
        target_val = node.get("value")

        actual_val = cls._resolve_field_value(field_name, record_data, old_record_data, diff)

        try:
            if op == "eq":
                return actual_val == target_val
            elif op == "neq":
                return actual_val != target_val
            elif op == "gt":
                return actual_val is not None and target_val is not None and actual_val > target_val
            elif op == "gte":
                return actual_val is not None and target_val is not None and actual_val >= target_val
            elif op == "lt":
                return actual_val is not None and target_val is not None and actual_val < target_val
            elif op == "lte":
                return actual_val is not None and target_val is not None and actual_val <= target_val
            elif op == "contains":
                if actual_val is None:
                    return False
                if isinstance(actual_val, (list, tuple, set)):
                    return target_val in actual_val
                return str(target_val) in str(actual_val)
            elif op == "icontains":
                if actual_val is None:
                    return False
                return str(target_val).lower() in str(actual_val).lower()
            elif op == "starts_with":
                if actual_val is None:
                    return False
                return str(actual_val).startswith(str(target_val))
            elif op == "ends_with":
                if actual_val is None:
                    return False
                return str(actual_val).endswith(str(target_val))
            elif op == "in":
                if target_val is None:
                    return False
                if isinstance(target_val, (list, tuple, set)):
                    return actual_val in target_val
                return actual_val == target_val
            elif op == "not_in":
                if target_val is None:
                    return True
                if isinstance(target_val, (list, tuple, set)):
                    return actual_val not in target_val
                return actual_val != target_val
            elif op == "between":
                if actual_val is None or not isinstance(target_val, (list, tuple)) or len(target_val) != 2:
                    return False
                low, high = target_val
                return low <= actual_val <= high
            elif op == "is_null":
                expected_null = bool(target_val)
                is_currently_null = actual_val is None
                return is_currently_null == expected_null
            else:
                logger.warning(f"Unsupported comparison operator '{op}' in TCA condition node")
                return False
        except Exception as exc:
            logger.error(f"Error evaluating condition node {node}: {exc}")
            return False

    @classmethod
    def _resolve_field_value(
        cls,
        field_path: str,
        record_data: Dict[str, Any],
        old_record_data: Optional[Dict[str, Any]] = None,
        diff: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Resolve dotted or prefixed field values from appropriate data snapshot."""
        if not field_path:
            return None

        # Check prefixed targets
        source = record_data
        actual_path = field_path

        if field_path.startswith("old:"):
            source = old_record_data or {}
            actual_path = field_path[4:]
        elif field_path.startswith("diff:"):
            source = diff or {}
            actual_path = field_path[5:]

        # Traverse dotted path (e.g. 'custom_fields.tier' or 'profile.city')
        parts = actual_path.split(".")
        current = source
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current
