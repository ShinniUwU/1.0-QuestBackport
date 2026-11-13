using System.Reflection;
using System.Text.Json;
using SPTarkov.Common.Models.Logging;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Helpers.Server;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Spt.Mod;
using SPTarkov.Server.Core.Models.Spt.Tables;
using Range = SemanticVersioning.Range;
using Version = SemanticVersioning.Version;

namespace QuestBackport;

public record ModMetadata : IModMetadata
{
    public string ModGuid { get; init; } = "com.shinniuwu.questsbackport";
    public string Name { get; init; } = "Shinni's 1.0 QuestsBackport";
    public string Author { get; init; } = "ShinniUwU";
    public List<string>? Contributors { get; init; }
    public Version Version { get; init; } = new("0.1.1");
    public Range SptVersion { get; init; } = new("~4.1.0");
    public List<string>? Incompatibilities { get; init; }
    public Dictionary<string, Range>? ModDependencies { get; init; } = new()
    {
        { "com.wtt.commonlib", new Range(">=3.0.0") },
    };
    public string? Url { get; init; } = "https://github.com/ShinniUwU/1.0-QuestBackport";
    public string License { get; init; } = "MIT";
    public bool HasPrepatcher { get; init; } = false;
}

// PostLoad + 5: after the database and WTT-ContentBackport's 1.0 items,
// and before RefFriendlyQuests (PostLoad + 14) so its Ref quest edits win.
[Injectable(InjectionType.Singleton, TypePriority = OnLoadOrder.PostLoad + 5)]
public class QuestBackportMod(
    ISptLogger<QuestBackportMod> logger,
    WTTServerCommonLib.WTTServerCommonLib wttCommon,
    TemplateTable templateTable,
    TradersTable tradersTable,
    ModHelper modHelper,
    IReadOnlyList<SptMod> loadedMods
) : IOnLoad
{
    private const string Tag = "[Shinni's 1.0 QuestsBackport]";

    // our quests that another mod's own version replaced
    private readonly HashSet<string> _replaced = [];

    public async Task OnLoadAsync(CancellationToken cancellationToken)
    {
        var assembly = Assembly.GetExecutingAssembly();
        await wttCommon.CustomQuestZoneService.CreateCustomQuestZones(assembly);
        await wttCommon.CustomLootspawnService.CreateCustomLootSpawns(assembly);
        // offers 1.0 quests unlock that SPT's traders don't stock; must exist before quest assorts point at them
        await wttCommon.CustomAssortSchemeService.CreateCustomAssortSchemes(assembly);
        await wttCommon.CustomQuestService.CreateCustomQuests(assembly);
        var modDir = modHelper.GetAbsolutePathToModFolder(assembly);
        await LoadOptional(assembly, modDir);
        ReportLoaded(modDir);
    }

    private record OptionalMod(string Mod, string Name, string Note);

    // db/Optional/<mod guid>/ holds quest versions that only make sense with that mod loaded:
    // the real Wedge instead of the Goons, Icebreaker's own quests instead of the Lighthouse stand-ins.
    private async Task LoadOptional(Assembly assembly, string modDir)
    {
        var root = Path.Combine(modDir, "db", "Optional");
        var index = Path.Combine(root, "index.json");
        if (!File.Exists(index))
            return;
        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        var entries = JsonSerializer.Deserialize<List<OptionalMod>>(File.ReadAllText(index), options) ?? [];
        var loaded = loadedMods.Select(m => m.ModMetadata.ModGuid).ToHashSet();
        var used = 0;
        foreach (var entry in entries.Where(e => loaded.Contains(e.Mod)))
        {
            var dir = Path.Combine(root, entry.Mod);
            if (Directory.Exists(Path.Combine(dir, "CustomQuests")))
                await wttCommon.CustomQuestService.CreateCustomQuests(assembly, Path.Combine("db", "Optional", entry.Mod, "CustomQuests"));
            var replaces = Path.Combine(dir, "replaces.json");
            if (File.Exists(replaces))
                Replace(JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(replaces)) ?? [], entry.Name);
            logger.Info($"{Tag} {entry.Name} found: {entry.Note}");
            used++;
        }

        if (used == 0)
            logger.Info($"{Tag} no optional mods found, using the stand-ins");
    }

    // The other mod ships the same quest under its own id. Drop ours and move our trader offers behind theirs.
    private void Replace(Dictionary<string, string> map, string modName)
    {
        var quests = templateTable.Quests;
        foreach (var (ours, theirs) in map)
        {
            if (!quests.ContainsKey(theirs))
            {
                logger.Warning($"{Tag} {modName} has no quest {theirs}, keeping our {ours}");
                continue;
            }

            quests.Remove(ours);
            _replaced.Add(ours);
            foreach (var trader in tradersTable.Values)
            {
                if (trader.QuestAssort == null)
                    continue;
                foreach (var locks in trader.QuestAssort.Values)
                foreach (var assort in locks.Where(l => l.Value == ours).Select(l => l.Key).ToList())
                    locks[assort] = new MongoId(theirs);
            }
        }
    }

    // WTT only logs on failure, so count what actually reached the quest table.
    private void ReportLoaded(string modDir)
    {
        var questDir = Path.Combine(modDir, "db", "CustomQuests");
        var quests = templateTable.Quests;
        int expected = 0, present = 0;
        foreach (var file in Directory.GetFiles(questDir, "*.json", SearchOption.AllDirectories))
        {
            if (!file.Contains($"{Path.DirectorySeparatorChar}Quests{Path.DirectorySeparatorChar}"))
                continue;
            using var doc = JsonDocument.Parse(File.ReadAllText(file));
            foreach (var quest in doc.RootElement.EnumerateObject())
            {
                if (_replaced.Contains(quest.Name))
                    continue;
                expected++;
                if (quests.ContainsKey(quest.Name))
                    present++;
                else
                    logger.Warning($"{Tag} quest {quest.Name} did not load");
            }
        }

        logger.Success($"{Tag} {present}/{expected} backported quests in the database");
    }
}
