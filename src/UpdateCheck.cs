using System.Text.Json;
using Version = SemanticVersioning.Version;

namespace QuestBackport;

// Asks the Forge for the newest published version of the mod.
public static class UpdateCheck
{
    public const string ForgeUrl = "https://sp-mod.com/mod/3340/shinnis-10-questsbackport";
    private const string ApiUrl = "https://sp-mod.com/api/v0/mod/3340?include=versions";

    public static async Task<Version?> GetNewerVersion(Version current, CancellationToken cancellationToken)
    {
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
        http.DefaultRequestHeaders.UserAgent.ParseAdd($"ShinnisQuestsBackport/{current}");
        http.DefaultRequestHeaders.Accept.ParseAdd("application/json");
        using var doc = JsonDocument.Parse(await http.GetStringAsync(ApiUrl, cancellationToken));
        return Newest(doc.RootElement, current);
    }

    // The Forge lists every published version; pick the highest one above ours.
    // Alphas and betas are only offered to people already running one.
    public static Version? Newest(JsonElement response, Version current)
    {
        Version? newest = null;
        foreach (var v in response.GetProperty("data").GetProperty("versions").EnumerateArray())
        {
            if (!v.TryGetProperty("version", out var s) || !Version.TryParse(s.GetString(), out var parsed))
                continue;
            if (parsed.IsPreRelease && !current.IsPreRelease)
                continue;
            if (newest == null || parsed > newest)
                newest = parsed;
        }
        return newest != null && newest > current ? newest : null;
    }
}
