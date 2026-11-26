using System.Collections.Concurrent;

namespace TripFlow.Backend;

internal sealed record PythonAttempt(int Status, ErrorDetail? Error = null);

internal sealed class PythonTaskWorker(PostgresStore store, PythonApiClient python, TimeProvider clock,
    IHostApplicationLifetime lifetime, ILogger<PythonTaskWorker> logger) : BackgroundService
{
    private readonly ConcurrentDictionary<Guid, Lazy<Task<PythonAttempt>>> _running = new();

    public bool IsConfigured => python.IsConfigured;

    public DateTimeOffset Deadline(DateTimeOffset now) => python.Deadline(now);

    public Task<PythonAttempt> Submit(PythonTask task, CancellationToken cancellationToken) =>
        task.Accepted ? Task.FromResult(new PythonAttempt(202)) : Advance(task.Id).WaitAsync(cancellationToken);

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var polling = new Dictionary<Guid, Task<PythonAttempt>>();
        try
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                foreach (var (id, operation) in polling.Where(entry => entry.Value.IsCompleted).ToArray())
                {
                    await operation;
                    polling.Remove(id);
                }

                var now = clock.GetUtcNow();
                var configured = IsConfigured;
                Guid[] due;
                try
                {
                    due = store.Read(data => data.PythonTasks
                        .Where(task => !task.Finished && (task.Deadline <= now
                            || (configured && (task.NextAttemptAt == null || task.NextAttemptAt <= now))))
                        .Select(task => task.Id).ToArray());
                }
                catch (Exception error) when (PostgresStore.IsUnavailable(error))
                {
                    logger.LogWarning("Could not read pending Python tasks from PostgreSQL.");
                    await Task.Delay(TimeSpan.FromSeconds(5), clock, stoppingToken);
                    continue;
                }
                foreach (var id in due.Where(id => !polling.ContainsKey(id)))
                    polling.Add(id, Advance(id));
                await Task.Delay(TimeSpan.FromSeconds(1), clock, stoppingToken);
            }
        }
        finally
        {
            await Task.WhenAll(polling.Values);
        }
    }

    // The request handler and the worker share one in-flight operation for each saved task.
    private Task<PythonAttempt> Advance(Guid taskId) =>
        _running.GetOrAdd(taskId, id => new(() => AdvanceOnce(id))).Value;

    private async Task<PythonAttempt> AdvanceOnce(Guid taskId)
    {
        var stopping = lifetime.ApplicationStopping;
        try
        {
            var match = store.Read(data => PythonTaskState.Find(data, taskId));
            if (match is not { } current)
                return new(404);
            var (card, task) = current;
            if (task.Finished)
                return PreviousAttempt(task);
            var now = clock.GetUtcNow();
            if (task.Deadline <= now || !PythonTaskState.IsCurrent(card, task))
                return SaveAttempt(taskId);
            if (!IsConfigured)
                return new(503);
            if (task.NextAttemptAt > now)
                return new(task.Accepted ? 202 : 502);

            // A disconnected browser stops waiting while the saved submission keeps running.
            using var token = CancellationTokenSource.CreateLinkedTokenSource(stopping);
            token.CancelAfter(task.Deadline - now);
            PythonResponse response;
            try
            {
                response = await python.Send(task, token.Token);
            }
            catch (OperationCanceledException) when (token.IsCancellationRequested && !stopping.IsCancellationRequested)
            {
                response = new(504, TimeSpan.Zero, Error: PythonTaskState.TimedOut);
            }
            return stopping.IsCancellationRequested ? new(503) : SaveAttempt(taskId, response);
        }
        catch (OperationCanceledException) when (stopping.IsCancellationRequested)
        {
            return new(503);
        }
        catch (Exception error) when (PostgresStore.IsUnavailable(error))
        {
            logger.LogWarning("Could not persist Python task {TaskId}.", taskId);
            return new(503, new("TASK_STORAGE_UNAVAILABLE", "Could not persist the Python task."));
        }
        finally
        {
            _running.TryRemove(taskId, out _);
        }
    }

    private PythonAttempt SaveAttempt(Guid taskId, PythonResponse? response = null)
    {
        var attempt = new PythonAttempt(404);
        store.Change(data =>
        {
            if (PythonTaskState.Find(data, taskId) is not { } match)
                return Results.NotFound();
            var (card, task) = match;
            if (task.Finished)
            {
                attempt = PreviousAttempt(task);
                return Results.Conflict();
            }
            if (!PythonTaskState.IsCurrent(card, task))
            {
                task.Finished = true;
                attempt = new(409);
                return Results.NoContent();
            }

            var now = clock.GetUtcNow();
            if (task.Deadline <= now)
                response = new(504, TimeSpan.Zero, Error: PythonTaskState.TimedOut);
            if (response is null)
                return Results.Conflict();

            attempt = new(response.Status, response.Error);
            if (response.PollPath is not null)
            {
                task.Accepted = true;
                task.PollPath = response.PollPath;
            }
            if (response.Error is not null)
                PythonTaskState.Fail(card, task, response.Error);
            else if (response.Result is { } result)
            {
                var invalid = PythonTaskResult.Apply(card, task, result);
                if (invalid is not null)
                    PythonTaskState.Fail(card, task, new("INVALID_PYTHON_RESULT", invalid));
                task.Finished = true;
            }
            else
            {
                if (task.NextAttemptAt is null)
                    task.PollPath ??= PythonApiClient.TaskPath(task.Id);
                var delay = response.Delay < TimeSpan.Zero ? TimeSpan.Zero : response.Delay;
                var remaining = task.Deadline - now;
                task.NextAttemptAt = now + (delay < remaining ? delay : remaining);
            }
            return Results.NoContent();
        });
        return attempt;
    }

    private PythonAttempt PreviousAttempt(PythonTask task) => task.Accepted
        ? new(202)
        : task.Deadline <= clock.GetUtcNow() ? new(504, PythonTaskState.TimedOut) : new(502);
}
