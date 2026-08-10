import { plainToInstance } from 'class-transformer';
import { validate, ValidationError } from 'class-validator';

import { CreateDimensionDto } from './create-dimension.dto.js';
import { UpdateDimensionDto } from './update-dimension.dto.js';
import { Numerical } from '../entities/dimensions.entity.js';

describe('Dimension tier contract', () => {
    const schedule = [
        { tierPosition: '1', upperBound: '100' },
        { tierPosition: '2', upperBound: '500', unitPrice: '0.25' },
        { tierPosition: '3', upperBound: 'inf', unitPrice: '0.10' },
    ];

    const dimension = (tiers: unknown, extra: Record<string, unknown> = {}) =>
        plainToInstance(CreateDimensionDto, {
            dimensionName: 'API requests',
            consumptionUnit: { unit: 'count-based', type: 'count' },
            usageIncrement: '10',
            rounding: 'ceiling',
            tiers,
            ...extra,
        });

    const messagesFor = async (value: object, property: string): Promise<string[]> => {
        const collect = (errors: ValidationError[]): string[] =>
            errors.flatMap((error) => [
                ...Object.values(error.constraints ?? {}),
                ...collect(error.children ?? []),
            ]);
        const errors = await validate(value);
        return collect(errors.filter((error) => error.property === property));
    };

    const expectRejected = async (value: object, property = 'tiers') => {
        expect(await messagesFor(value, property)).not.toHaveLength(0);
    };

    it('accepts an ordered schedule with an optional free first tier', async () => {
        const value = dimension(schedule);
        await expect(messagesFor(value, 'tiers')).resolves.toEqual([]);
        const malformed = dimension([{ tierPosition: '1', upperBound: 'not-a-number' }]);
        await expectRejected(malformed);
    });

    it('rejects finite bounds that do not align to the usage increment', async () => {
        const value = dimension([
            schedule[0],
            { tierPosition: '2', upperBound: '205', unitPrice: '0.25' },
        ]);
        await expectRejected(value);
    });

    it('rejects descending or overlapping bounds', async () => {
        const value = dimension([
            { tierPosition: '1', upperBound: '200' },
            { tierPosition: '2', upperBound: '100', unitPrice: '0.25' },
        ]);
        await expectRejected(value);
    });

    it('requires an infinite bound to be the final tier', async () => {
        const value = dimension([
            { tierPosition: '1', upperBound: 'inf' },
            { tierPosition: '2', upperBound: '200', unitPrice: '0.25' },
        ]);
        await expectRejected(value);
    });

    it('rejects tier schedules combined with legacy pricing fields', async () => {
        await expectRejected(dimension(schedule, { consumptionPrice: '2.00' }));
        await expectRejected(dimension(schedule, { usageEntitlement: 100 }));
        await expectRejected(dimension(schedule, { overageAllowed: 'true' }));
    });

    it('requires a price on every tier after the first', async () => {
        const value = dimension([
            schedule[0],
            { tierPosition: '2', upperBound: 'inf' },
        ]);
        await expectRejected(value);
    });

    it('persists and restores a schedule without changing its values', () => {
        const point = { tag: jest.fn() };
        point.tag.mockReturnValue(point);
        const numerical = {
            numericalType: 'float',
            dimensionUnit: 'count-based',
            dimensionUnitType: 'count',
            aggregationInterval: 'hour',
            aggregationMethod: 'sum',
            priceSegments: [{ lowerLimit: '0', upperLimit: 'inf', price: '0' }],
            sampleType: 'gauge',
            usageIncrement: 10,
            rounding: 'ceiling',
            tiers: schedule,
        } as any;

        Numerical.transformer(numerical, point as any);
        expect(point.tag).toHaveBeenCalledWith('tiers', JSON.stringify(schedule));

        const restored = Numerical.dbModelToEntity({
            ...numerical,
            priceSegments: JSON.stringify(numerical.priceSegments),
            usageIncrement: '10',
            tiers: JSON.stringify(schedule),
        });
        expect(restored.tiers).toEqual(schedule);
    });

    it('includes persisted tiers when constructing a read DTO', () => {
        const dto = new CreateDimensionDto({
            dimensionName: 'API requests',
            measurementId: 'measurement-id',
            metadata: {},
            numerical: {
                dimensionUnit: 'count-based',
                dimensionUnitType: 'count',
                aggregationInterval: 'hour',
                aggregationMethod: 'sum',
                priceSegments: [{ lowerLimit: '0', upperLimit: 'inf', price: '0' }],
                usageIncrement: 10,
                rounding: 'ceiling',
                tiers: schedule,
            },
        } as any);
        expect(dto.tiers).toEqual(schedule);
    });

    it('accepts null as the explicit clear operation on update', async () => {
        const malformedReplacement = plainToInstance(UpdateDimensionDto, {
            tiers: [{ tierPosition: '1', upperBound: 'not-a-number' }],
        });
        await expectRejected(malformedReplacement);
        const update = plainToInstance(UpdateDimensionDto, { tiers: null });
        await expect(messagesFor(update, 'tiers')).resolves.toEqual([]);
    });
});
