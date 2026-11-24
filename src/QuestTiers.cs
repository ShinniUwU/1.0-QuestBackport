using System.Text.Json;

namespace QuestBackport;

// db/QuestTiers.json, written by tools/build.py. 1.0 unlocks many quests once you've done N quests for a
// trader at a loyalty level ("finish 3 Prapor quests at LL1"). The 0.16.9 client can't count that, so the
// server keeps those quests hidden until then. A quest counts for the loyalty level it unlocks at.
public sealed class QuestTiers<TId> where TId : notnull
{
    public record Lock(string Trader, int Level, int Count);

    private record TiersFile(Dictionary<string, Lock>? Locks, Dictionary<string, Dictionary<string, List<string>>>? Counted);

    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true };

    private readonly Dictionary<TId, Lock> _locks = new();
    private readonly Dictionary<(string Trader, int Level), HashSet<TId>> _counted = new();

    public int Count => _locks.Count;

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
        return tiers;
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
    }
}
