using System.Text.Json;

namespace QuestBackport;

// db/QuestTiers.json, written by tools/build.py. 1.0 unlocks many quests once you've done N quests for a
// trader at a loyalty level ("finish 3 Prapor quests at LL1"). The 0.16.9 client can't count that, so the
// server keeps those quests hidden until then. A quest counts for the loyalty level it unlocks at.
public sealed class QuestTiers<TId> where TId : notnull
{
    public record Lock(string Trader, int Level, int Count);

    // after: the old prerequisites and the statuses that count; later: the quests 1.0 puts after this one
    private record OldOrderFile(Dictionary<string, List<int>>? After, List<string>? Later);

    private sealed class OldOrder
    {
        public Dictionary<TId, HashSet<int>> After = new();
        public HashSet<TId> Later = new();
    }

    private record TiersFile(
        Dictionary<string, Lock>? Locks,
        Dictionary<string, Dictionary<string, List<string>>>? Counted,
        Dictionary<string, OldOrderFile>? OldOrder
    );

    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };

    private readonly Dictionary<TId, Lock> _locks = new();
    private readonly Dictionary<(string Trader, int Level), HashSet<TId>> _counted = new();
    private readonly Dictionary<TId, OldOrder> _oldOrder = new();

    public int Count => _locks.Count;
    public int OldOrderCount => _oldOrder.Count;

    public static QuestTiers<TId>? Load(string path, Func<string, TId> id)
    {
        if (!File.Exists(path))
            return null;
        var file = JsonSerializer.Deserialize<TiersFile>(File.ReadAllText(path), Options);
        var tiers = new QuestTiers<TId>();
        foreach (var (quest, lk) in file?.Locks ?? [])
            tiers._locks[id(quest)] = lk;
        foreach (var (trader, levels) in file?.Counted ?? [])
        foreach (var (level, quests) in levels)
            tiers._counted[(trader, int.Parse(level))] = quests.Select(id).ToHashSet();
        foreach (var (quest, o) in file?.OldOrder ?? [])
            tiers._oldOrder[id(quest)] = new OldOrder
            {
                After = (o.After ?? []).ToDictionary(a => id(a.Key), a => a.Value.ToHashSet()),
                Later = (o.Later ?? []).Select(id).ToHashSet(),
            };
        return tiers;
    }

    // 1.0 moved this quest ahead of its old prerequisite (The Punisher - Part 1 was SPT's Part 3). A profile
    // that already has a quest 1.0 puts after it is on the chain the old way, so it waits for the old one.
    // statuses: the profile's quests and their status
    public bool WaitsForOldOrder(TId quest, IReadOnlyDictionary<TId, int> statuses)
    {
        if (!_oldOrder.TryGetValue(quest, out var o) || !o.Later.Any(statuses.ContainsKey))
            return false;
        foreach (var (before, ok) in o.After)
            if (!statuses.TryGetValue(before, out var s) || !ok.Contains(s))
                return true;
        return false;
    }

    // finished: the quests the player has completed
    public bool IsLocked(TId quest, ISet<TId> finished)
    {
        if (!_locks.TryGetValue(quest, out var lk) || lk.Count <= 0)
            return false;
        if (!_counted.TryGetValue((lk.Trader, lk.Level), out var counted))
            return true;
        var done = 0;
        foreach (var q in counted)
            if (finished.Contains(q) && ++done >= lk.Count)
                return false;
        return true;
    }

    // another mod ships the same quest under its own id
    public void Rename(TId ours, TId theirs)
    {
        if (_locks.Remove(ours, out var lk))
            _locks[theirs] = lk;
        foreach (var counted in _counted.Values)
            if (counted.Remove(ours))
                counted.Add(theirs);
        if (_oldOrder.Remove(ours, out var o))
            _oldOrder[theirs] = o;
        foreach (var other in _oldOrder.Values)
        {
            if (other.After.Remove(ours, out var ok))
                other.After[theirs] = ok;
            if (other.Later.Remove(ours))
                other.Later.Add(theirs);
        }
    }
}
