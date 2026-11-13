using System.Collections.Concurrent;
using System.Reflection;
using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Controllers;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Services.Commerce;

namespace QuestBackport;

// After a player's game starts, send them the update notice once per server run.
public class LoginNoticePatch : AbstractPatch
{
    internal static MailSendService? Mail;
    internal static volatile string? Message;
    private static readonly ConcurrentDictionary<MongoId, byte> Told = new();

    protected override MethodBase? GetTargetMethod()
    {
        return typeof(GameController).GetMethod(nameof(GameController.GameStart));
    }

    [PatchPostfix]
    public static void Postfix(MongoId sessionId)
    {
        var message = Message;
        if (message == null || Mail == null || !Told.TryAdd(sessionId, 0))
            return;
        try
        {
            Mail.SendSystemMessageToPlayer(sessionId, message, null);
        }
        catch
        {
            // never let the notice break logging in
        }
    }
}
