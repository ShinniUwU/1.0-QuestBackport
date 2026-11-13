using System.Text.Json;
using SPTarkov.Common.Models.Logging;

namespace QuestBackport;

// config.json next to the mod's dll. Missing or broken file means defaults.
public record ModConfig
{
    public bool CheckForUpdates { get; init; } = true;
    public bool NotifyInGame { get; init; } = true;

    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    public static ModConfig Load<T>(string path, ISptLogger<T> logger)
    {
        if (!File.Exists(path))
            return new ModConfig();
        try
        {
            return JsonSerializer.Deserialize<ModConfig>(File.ReadAllText(path), Options) ?? new ModConfig();
        }
        catch (JsonException e)
        {
            logger.Warning($"[Shinni's 1.0 QuestsBackport] config.json is invalid, using defaults: {e.Message}");
            return new ModConfig();
        }
    }
}
