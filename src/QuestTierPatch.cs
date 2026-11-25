using System.Reflection;
using SPTarkov.Common.Models.Logging;
using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Helpers.Profile;
using SPTarkov.Server.Core.Helpers.Quest;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common.Tables;
using SPTarkov.Server.Core.Models.Enums;

namespace QuestBackport;

// The quest list SPT sends the client. Leaves out the quests 1.0 unlocks once enough quests are done at a
// loyalty level until they are, and quests 1.0 reordered from profiles still on the old order. Quests the
// profile already has stay, whatever unlocked them.
public class QuestTierPatch : AbstractPatch
{
    internal static QuestTiers<MongoId>? Tiers;
    internal static ProfileHelper? Profiles;
    internal static ISptLogger<QuestBackportMod>? Logger;
    private static bool _warned;

    protected override MethodBase? GetTargetMethod()
    {
        return typeof(QuestHelper).GetMethod(nameof(QuestHelper.GetClientQuests));
    }

    [PatchPostfix]
    public static void Postfix(MongoId sessionId, ref List<Quest> __result)
    {
        var tiers = Tiers;
        if (tiers == null || Profiles == null || __result == null)
            return;
        try
        {
            var statuses = Profiles.GetPmcProfile(sessionId)?.Quests;
            if (statuses == null)
                return;
            var known = new Dictionary<MongoId, int>();
            var finished = new HashSet<MongoId>();
            foreach (var s in statuses)
            {
                if (s.Status != QuestStatusEnum.Locked)
                    known[s.QId] = (int)s.Status;
                if (s.Status == QuestStatusEnum.Success)
                    finished.Add(s.QId);
            }

            __result = __result
                .Where(q => known.ContainsKey(q.Id) || (!tiers.IsLocked(q.Id, finished) && !tiers.WaitsForOldOrder(q.Id, known)))
                .ToList();
        }
        catch (Exception e)
        {
            // never let this break the quest list
            if (_warned)
                return;
            _warned = true;
            Logger?.Warning($"[Shinni's 1.0 QuestsBackport] quest unlock counting failed, showing every quest: {e.Message}");
        }
    }
}
