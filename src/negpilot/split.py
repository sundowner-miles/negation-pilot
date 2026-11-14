"""Split base cases, never individual rows."""

from __future__ import annotations

import math
import random
from collections import defaultdict


def compute_targets(count: int, fractions: dict[str, float]) -> dict[str, int]:
    splits = ("train", "dev", "test")
    if set(fractions) != set(splits):
        raise ValueError("split fractions must define train, dev, and test")
    if abs(sum(fractions[item] for item in splits) - 1.0) > 1e-9:
        raise ValueError("split fractions must sum to 1")
    raw = {name: count * fractions[name] for name in splits}
    floors = {name: math.floor(raw[name]) for name in splits}
    remainder = count - sum(floors.values())
    order = sorted(splits, key=lambda name: (raw[name] - floors[name], name), reverse=True)
    for name in order[:remainder]:
        floors[name] += 1
    return floors


def _hamilton(group_size: int, targets: dict[str, int], total: int) -> dict[str, int]:
    splits = ("train", "dev", "test")
    raw = {name: group_size * targets[name] / total for name in splits}
    floors = {name: math.floor(raw[name]) for name in splits}
    remainder = group_size - sum(floors.values())
    order = sorted(splits, key=lambda name: (raw[name] - floors[name], name), reverse=True)
    for name in order[:remainder]:
        floors[name] += 1
    if sum(floors.values()) != group_size:
        raise RuntimeError("Hamilton allocation does not cover the stratum")
    return floors


def assign_splits(
    base_case_ids: list[str],
    strata: list[str],
    seed: int,
    fractions: dict[str, float],
) -> dict[str, str]:
    """Assign each base case to one split.

    Both members of a pair share a base_case_id, so they stay together.
    Within each stratum the seed shuffles order. Counts follow largest-remainder
    allocation and are repaired until the global totals match the fractions.
    """
    if len(base_case_ids) != len(strata):
        raise ValueError("strata must align with base_case_ids")
    if len(set(base_case_ids)) != len(base_case_ids):
        raise ValueError("duplicate base_case_id")
    total = len(base_case_ids)
    targets = compute_targets(total, fractions)
    grouped: dict[str, list[str]] = defaultdict(list)
    for base_id, stratum in zip(base_case_ids, strata):
        grouped[stratum].append(base_id)
    rng = random.Random(seed)
    for key in sorted(grouped):
        rng.shuffle(grouped[key])

    alloc = {
        key: _hamilton(len(grouped[key]), targets, total) for key in sorted(grouped)
    }
    splits = ("train", "dev", "test")

    def totals() -> dict[str, int]:
        got = {name: 0 for name in splits}
        for counts in alloc.values():
            for name in splits:
                got[name] += counts[name]
        return got

    guard = 0
    while totals() != targets:
        guard += 1
        if guard > total * 4:
            raise RuntimeError("split repair did not converge")
        got = totals()
        donors = [name for name in splits if got[name] > targets[name]]
        receivers = [name for name in splits if got[name] < targets[name]]
        if not donors or not receivers:
            raise RuntimeError(f"split repair stuck at {got} versus {targets}")
        moved = False
        for key in sorted(alloc):
            for donor in donors:
                if alloc[key][donor] <= 0:
                    continue
                receiver = receivers[0]
                alloc[key][donor] -= 1
                alloc[key][receiver] += 1
                moved = True
                break
            if moved:
                break
        if not moved:
            raise RuntimeError("no stratum could donate a base case to the short split")

    mapping: dict[str, str] = {}
    for key in sorted(grouped):
        cursor = 0
        ordered = grouped[key]
        for name in splits:
            take = alloc[key][name]
            for base_id in ordered[cursor : cursor + take]:
                mapping[base_id] = name
            cursor += take
        if cursor != len(ordered):
            raise RuntimeError("stratum was not fully assigned")
    return mapping


def assign_skeleton_splits(
    base_case_ids: list[str],
    skeleton_keys: list[str],
    seed: int,
    fractions: dict[str, float],
) -> dict[str, str]:
    """Put every copy of one alpha-renamed skeleton into a single split.

    Splitting a skeleton across train and test would leak the logical pattern
    through a letter substitution. Group sizes are therefore atomic.
    """
    if len(base_case_ids) != len(skeleton_keys):
        raise ValueError("skeleton keys must align with base_case_ids")
    grouped: dict[str, list[str]] = defaultdict(list)
    for base_id, key in zip(base_case_ids, skeleton_keys):
        grouped[key].append(base_id)
    items = sorted(grouped, key=lambda key: (len(grouped[key]), key))
    rng = random.Random(seed)
    rng.shuffle(items)
    sizes = [len(grouped[key]) for key in items]
    targets = compute_targets(sum(sizes), fractions)
    choice = _dp_assign(sizes, targets["dev"], targets["test"])
    if choice is None:
        raise RuntimeError(
            "Skeleton groups cannot meet the split quotas without cutting a group. "
            f"Targets are {targets}. Group sizes are {sorted(sizes, reverse=True)}."
        )
    mapping: dict[str, str] = {}
    for key, split_name in zip(items, choice):
        for base_id in grouped[key]:
            mapping[base_id] = split_name
    return mapping


def _largest_remainder(counts: dict[str, int], fractions: dict[str, float]) -> dict[str, dict[str, int]]:
    """Split each feature count across train/dev/test without changing its total."""
    splits = ("train", "dev", "test")
    targets = {name: {} for name in splits}
    for key, count in counts.items():
        raw = {name: count * fractions[name] for name in splits}
        floors = {name: math.floor(raw[name]) for name in splits}
        remainder = count - sum(floors.values())
        order = sorted(splits, key=lambda name: (raw[name] - floors[name], name), reverse=True)
        for name in order[:remainder]:
            floors[name] += 1
        for name in splits:
            targets[name][key] = floors[name]
    return targets


def assign_balanced_splits(
    groups: list[dict],
    seed: int,
    fractions: dict[str, float],
    dimensions: list[str],
) -> tuple[dict[str, str], dict[str, int]]:
    """Assign whole groups to splits.

    ``groups`` items have ``key``, ``size`` (base cases), and ``features``
    mapping a dimension name to a count dict. Group keys stay intact.
    Exact base-case quotas are kept when a feasible packing exists. Feature
    targets are largest-remainder shares of the observed margins.
    """
    if not groups:
        return {}, compute_targets(0, fractions)
    splits = ("train", "dev", "test")
    base_targets = compute_targets(sum(item["size"] for item in groups), fractions)
    margins: dict[str, dict[str, int]] = {name: defaultdict(int) for name in dimensions}
    for group in groups:
        for name in dimensions:
            for key, count in group["features"].get(name, {}).items():
                margins[name][str(key)] += int(count)
    feature_targets = {
        name: _largest_remainder(dict(margins[name]), fractions) for name in dimensions
    }
    weights = {
        "label": 8,
        "position": 8,
        "depth": 8,
        "scope": 2,
        "polarity": 3,
        "family": 3,
        "control": 3,
        "critical": 3,
        "pair_type": 1,
    }

    def empty_counts() -> dict[str, dict[str, dict[str, int]]]:
        return {
            name: {split_name: defaultdict(int) for split_name in splits} for name in dimensions
        }

    def score_of(counts: dict[str, dict[str, dict[str, int]]]) -> int:
        return _balance_score(counts, dimensions, feature_targets, weights)

    def add_group(counts, bases, group, split_name, sign: int) -> None:
        bases[split_name] += sign * group["size"]
        for name in dimensions:
            bucket = counts[name][split_name]
            for key, count in group["features"].get(name, {}).items():
                bucket[str(key)] += sign * int(count)

    def pack(order: list[dict]) -> tuple[dict[str, str], int] | None:
        counts = empty_counts()
        bases = {name: 0 for name in splits}
        mapping: dict[str, str] = {}
        for group in order:
            options = [
                name for name in splits if bases[name] + group["size"] <= base_targets[name]
            ]
            if not options:
                return None
            best_name = None
            best_delta = None
            for name in options:
                before = score_of(counts)
                add_group(counts, bases, group, name, 1)
                delta = score_of(counts) - before
                add_group(counts, bases, group, name, -1)
                if best_delta is None or delta < best_delta or (delta == best_delta and name < best_name):
                    best_delta = delta
                    best_name = name
            assert best_name is not None
            add_group(counts, bases, group, best_name, 1)
            mapping[group["key"]] = best_name
        if bases != base_targets:
            return None
        return mapping, score_of(counts)

    if len(groups) <= 30:
        exact = _exact_assignment(groups, base_targets, dimensions, feature_targets, weights)
        if exact is not None:
            return exact
    rng = random.Random(seed)
    indexed = list(groups)
    for group in indexed:
        group["_tie"] = rng.random()
    orders = []
    largest_first = sorted(indexed, key=lambda group: (-group["size"], group["_tie"], group["key"]))
    orders.append(largest_first)
    for _ in range(7):
        shuffled = list(indexed)
        rng.shuffle(shuffled)
        orders.append(sorted(shuffled, key=lambda group: (-group["size"], group["_tie"])))
    best: tuple[dict[str, str], int] | None = None
    for order in orders:
        packed = pack(order)
        if packed is not None and (best is None or packed[1] < best[1]):
            best = packed

    sizes = [group["size"] for group in largest_first]
    choice = _dp_assign(sizes, base_targets["dev"], base_targets["test"])
    if choice is not None:
        mapping = {
            group["key"]: split_name for group, split_name in zip(largest_first, choice)
        }
        refined, refined_score = _hill_climb(
            indexed, mapping, dimensions, feature_targets, weights, seed
        )
        if best is None or refined_score < best[1]:
            best = refined, refined_score
    if best is None:
        raise RuntimeError(
            "Groups cannot meet the base-case split quotas without cutting a group. "
            f"Targets are {base_targets}. Sizes are {sorted(sizes, reverse=True)}."
        )
    return best[0], base_targets


def _balance_score(counts, dimensions, feature_targets, weights) -> int:
    """L1 distance plus a penalty for a split that entirely misses a targeted cell.

    The penalty makes a swap that introduces the first FACT or depth cell win
    even when the raw counts are otherwise tied. It does not split a group.
    """
    splits = ("train", "dev", "test")
    total = 0
    for name in dimensions:
        weight = weights.get(name, 1)
        for split_name in splits:
            keys = set(feature_targets[name][split_name]) | set(counts[name][split_name])
            for key in keys:
                got = counts[name][split_name][key]
                target = feature_targets[name][split_name].get(key, 0)
                total += weight * abs(got - target)
                if name in {"label", "position", "depth"} and target > 0 and got == 0:
                    total += 200
    return total


def _exchange(groups, mapping, dimensions, feature_targets, weights):
    """Swap up to three whole groups when their sizes match and the score falls."""
    from itertools import combinations

    current = dict(mapping)
    while True:
        score = _mapping_score(groups, current, dimensions, feature_targets, weights)
        by_split: dict[str, list[dict]] = defaultdict(list)
        for group in groups:
            by_split[current[group["key"]]].append(group)
        buckets: dict[int, dict[str, list[tuple[dict, ...]]]] = defaultdict(lambda: defaultdict(list))
        for split_name, members in by_split.items():
            for width in (1, 2, 3):
                if len(members) < width:
                    continue
                for combo in combinations(members, width):
                    buckets[sum(group["size"] for group in combo)][split_name].append(combo)
        improved = False
        for size_buckets in buckets.values():
            split_names = [name for name in ("dev", "test", "train") if size_buckets.get(name)]
            for left_index, left_name in enumerate(split_names):
                for right_name in split_names[left_index + 1 :]:
                    for left in size_buckets[left_name]:
                        for right in size_buckets[right_name]:
                            for group in left:
                                current[group["key"]] = right_name
                            for group in right:
                                current[group["key"]] = left_name
                            updated = _mapping_score(groups, current, dimensions, feature_targets, weights)
                            if updated < score:
                                improved = True
                                break
                            for group in left:
                                current[group["key"]] = left_name
                            for group in right:
                                current[group["key"]] = right_name
                        if improved:
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            return current


def _exact_assignment(groups, base_targets, dimensions, feature_targets, weights):
    """Pick the dev packing by exhaustive subset search, then balance the rest.

    A few dozen atomic groups make every dev subset that hits the quota cheap
    to list. The complementary test/train packing is then improved by swaps.
    """
    dev_need = base_targets["dev"]
    test_need = base_targets["test"]
    groups = sorted(groups, key=lambda group: (-group["size"], group["key"]))
    subsets: list[tuple[int, ...]] = []

    def collect(index: int, left: int, chosen: list[int]) -> None:
        if left == 0:
            subsets.append(tuple(chosen))
            return
        if index == len(groups) or left < 0:
            return
        chosen.append(index)
        collect(index + 1, left - groups[index]["size"], chosen)
        chosen.pop()
        collect(index + 1, left, chosen)

    collect(0, dev_need, [])
    if not subsets:
        return None
    ranked = sorted(subsets, key=lambda subset: _subset_score(
        groups, subset, "dev", dimensions, feature_targets, weights
    ))
    best = None
    for subset in ranked[:40]:
        mapping = {groups[index]["key"]: "dev" for index in subset}
        rest = [group for index, group in enumerate(groups) if index not in set(subset)]
        def score_rest(rest_mapping: dict[str, str]) -> int:
            full = dict(mapping)
            full.update(rest_mapping)
            return _mapping_score(groups, full, dimensions, feature_targets, weights)

        packed = _pack_two_way(
            rest, test_need, "test", "train", score_rest
        )
        if packed is None:
            continue
        mapping.update(packed)
        score = _mapping_score(groups, mapping, dimensions, feature_targets, weights)
        if best is None or score < best[1]:
            best = mapping, score
    if best is None:
        return None
    mapping = _exchange(groups, best[0], dimensions, feature_targets, weights)
    return mapping, _mapping_score(groups, mapping, dimensions, feature_targets, weights)


def _subset_score(groups, subset, split_name, dimensions, feature_targets, weights) -> int:
    counts = {
        name: {slot: defaultdict(int) for slot in ("train", "dev", "test")} for name in dimensions
    }
    for index in subset:
        for name in dimensions:
            for key, count in groups[index]["features"].get(name, {}).items():
                counts[name][split_name][str(key)] += int(count)
    return _balance_score(counts, dimensions, feature_targets, weights)


def _mapping_score(groups, mapping, dimensions, feature_targets, weights) -> int:
    counts = {
        name: {slot: defaultdict(int) for slot in ("train", "dev", "test")} for name in dimensions
    }
    for group in groups:
        split_name = mapping[group["key"]]
        for name in dimensions:
            for key, count in group["features"].get(name, {}).items():
                counts[name][split_name][str(key)] += int(count)
    return _balance_score(counts, dimensions, feature_targets, weights)


def _pack_two_way(groups, primary_need, primary, secondary, score_fn):
    """Assign ``groups`` to two splits with an exact size for the primary split."""
    if sum(group["size"] for group in groups) < primary_need:
        return None
    groups = sorted(groups, key=lambda group: (-group["size"], group["key"]))
    subsets: list[tuple[int, ...]] = []

    def collect(index: int, left: int, chosen: list[int]) -> None:
        if left == 0:
            subsets.append(tuple(chosen))
            return
        if index == len(groups) or left < 0:
            return
        chosen.append(index)
        collect(index + 1, left - groups[index]["size"], chosen)
        chosen.pop()
        collect(index + 1, left, chosen)

    collect(0, primary_need, [])
    if not subsets:
        return None
    best = None
    for subset in subsets:
        chosen = set(subset)
        mapping = {
            group["key"]: primary if index in chosen else secondary
            for index, group in enumerate(groups)
        }
        score = score_fn(mapping)
        if best is None or score < best[0]:
            best = score, mapping
    assert best is not None
    return best[1]


def _hill_climb(
    groups: list[dict],
    mapping: dict[str, str],
    dimensions: list[str],
    feature_targets: dict[str, dict[str, dict[str, int]]],
    weights: dict[str, int],
    seed: int,
) -> tuple[dict[str, str], int]:
    splits = ("train", "dev", "test")
    counts: dict[str, dict[str, dict[str, int]]] = {
        name: {split_name: defaultdict(int) for split_name in splits} for name in dimensions
    }
    for group in groups:
        split_name = mapping[group["key"]]
        for name in dimensions:
            for key, count in group["features"].get(name, {}).items():
                counts[name][split_name][str(key)] += int(count)

    def objective() -> int:
        return _balance_score(counts, dimensions, feature_targets, weights)

    def move(group: dict, source: str, target: str) -> None:
        for name in dimensions:
            for key, count in group["features"].get(name, {}).items():
                counts[name][source][str(key)] -= int(count)
                counts[name][target][str(key)] += int(count)
        mapping[group["key"]] = target

    by_size: dict[int, list[dict]] = defaultdict(list)
    for group in groups:
        by_size[group["size"]].append(group)
    rng = random.Random(seed + 17)
    improved = True
    passes = 0
    while improved and passes < 12:
        improved = False
        passes += 1
        for size, bucket in sorted(by_size.items()):
            order = list(bucket)
            rng.shuffle(order)
            for left_index, left in enumerate(order):
                for right in order[left_index + 1 :]:
                    left_split = mapping[left["key"]]
                    right_split = mapping[right["key"]]
                    if left_split == right_split:
                        continue
                    before = objective()
                    move(left, left_split, right_split)
                    move(right, right_split, left_split)
                    if objective() < before:
                        improved = True
                    else:
                        move(left, right_split, left_split)
                        move(right, left_split, right_split)
    return mapping, objective()


def _dp_assign(sizes: list[int], dev_target: int, test_target: int) -> list[str] | None:
    frontier = {(0, 0)}
    come: list[dict[tuple[int, int], tuple[int, int, str]]] = [{}]
    for size in sizes:
        nxt: dict[tuple[int, int], tuple[int, int, str]] = {}
        for dev_count, test_count in frontier:
            options = (
                ("train", dev_count, test_count),
                ("dev", dev_count + size, test_count),
                ("test", dev_count, test_count + size),
            )
            for label, next_dev, next_test in options:
                if next_dev > dev_target or next_test > test_target:
                    continue
                slot = (next_dev, next_test)
                if slot not in nxt:
                    nxt[slot] = (dev_count, test_count, label)
        frontier = set(nxt)
        come.append(nxt)
        if not frontier:
            return None
    if (dev_target, test_target) not in frontier:
        return None
    labels = [""] * len(sizes)
    dev_count, test_count = dev_target, test_target
    for index in range(len(sizes), 0, -1):
        previous_dev, previous_test, label = come[index][(dev_count, test_count)]
        labels[index - 1] = label
        dev_count, test_count = previous_dev, previous_test
    return labels
