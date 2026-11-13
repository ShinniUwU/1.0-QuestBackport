using System.Reflection;
using System.Text.Json;
using SPTarkov.Common.Models.Logging;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Helpers.Server;
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
    ModHelper modHelper
) : IOnLoad
{
    public async Task OnLoadAsync(CancellationToken cancellationToken)
    {
        var assembly = Assembly.GetExecutingAssembly();
        await wttCommon.CustomQuestZoneService.CreateCustomQuestZones(assembly);
        await wttCommon.CustomLootspawnService.CreateCustomLootSpawns(assembly);
        // offers 1.0 quests unlock that SPT's traders don't stock; must exist before quest assorts point at them
        await wttCommon.CustomAssortSchemeService.CreateCustomAssortSchemes(assembly);
        await wttCommon.CustomQuestService.CreateCustomQuests(assembly);
        ReportLoaded(modHelper.GetAbsolutePathToModFolder(assembly));
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
                expected++;
                if (quests.ContainsKey(quest.Name))
                    present++;
                else
                    logger.Warning($"[Shinni's 1.0 QuestsBackport] quest {quest.Name} did not load");
            }
        }

        logger.Success($"[Shinni's 1.0 QuestsBackport] {present}/{expected} backported quests in the database");
    }
}
