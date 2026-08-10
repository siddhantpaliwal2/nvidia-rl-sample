import { ConflictException } from '@nestjs/common';

import { PublicAPICustomerController } from './customer.controller';
import { CustomerService } from './customer.service';
import { CustomerEntity } from './entities/customer.entity';
import { MeasurementFormat } from '../measurement-config/entities/measurement.interface';
import { StandardMeasurementEntity } from '../measurement-config/entities/standardMeasurement.entity';
import {
    PreProcessorMeasurementType,
    StandardMeasurementPreProcessorEntity,
} from '../measurement-config/entities/standardMeasurementPreProcessor';
import { OfferingService } from '../offering/offering.service';
import { UsageService } from '../usage/usage.service';

describe('Customer identity migration', () => {
    afterEach(() => jest.restoreAllMocks());

    // These services use Nest constructor injection, whose positional order is
    // not part of the public migration contract. Give every non-Influx slot a
    // capability-complete double so equivalent dependency layouts are graded
    // by behavior rather than by matching the historical constructor exactly.
    const serviceDependencies = (overrides: Record<string, unknown> = {}) => ({
        create: jest.fn(),
        findOne: jest.fn(),
        findUsageForCustomer: jest.fn(),
        findAllCustomersWithOfferingId: jest.fn(async () => ({ data: [] })),
        findAllServicesWithCustomerId: jest.fn(async () => ({ data: [] })),
        ...overrides,
    });

    it('persists and restores the offering attached to a customer', () => {
        const point = { tag: jest.fn(), stringField: jest.fn() };
        const entity = new CustomerEntity({
            customerId: 'customer-1',
            businessID: 'business-1',
            customerName: 'Acme',
            paymentChannel: 'manual',
            offeringId: 'offering-1',
        } as any);
        CustomerEntity.transformer(entity, { getPoint: jest.fn(() => point) } as any);
        expect(point.tag).toHaveBeenCalledWith('offeringId', 'offering-1');

        const restored = CustomerEntity.dbModelToEntity({
            _value: 'Acme',
            customerId: 'customer-1',
            paymentChannel: 'manual',
            offeringId: 'offering-1',
        });
        expect(restored.offeringId).toBe('offering-1');
    });

    it('writes and reads standard measurements with customerId as the ownership tag', () => {
        const point = { timestamp: jest.fn(), tag: jest.fn(), floatField: jest.fn() };
        const measurement = new StandardMeasurementEntity({
            businessID: 'business-1',
            customerId: 'customer-1',
            dimensionId: 'dimension-1',
            recordValue: 4.5,
            metadata: { source: 'api' },
            timeStamp: '2023-03-10T00:00:00.000Z',
            _measurement: 'Usage',
        } as any);
        MeasurementFormat.getPointForm(measurement, { getPoint: jest.fn(() => point) } as any);
        expect(point.tag).toHaveBeenCalledWith('customerId', 'customer-1');
        expect(point.tag).toHaveBeenCalledWith('dimensionId', 'dimension-1');

        expect(
            MeasurementFormat.toEntity({
                _time: '2023-03-10T00:00:00.000Z',
                _measurement: 'Usage',
                _value: 4.5,
                businessID: 'business-1',
                customerId: 'customer-1',
                dimensionId: 'dimension-1',
                metadata_source: 'api',
            } as any),
        ).toEqual(expect.objectContaining({ customerId: 'customer-1', metadata: { source: 'api' } }));
    });

    it('maps infrastructure labels to customer-owned measurements', async () => {
        const publish = jest.spyOn(StandardMeasurementEntity, 'publish').mockReturnValue({} as any);
        const input = new StandardMeasurementPreProcessorEntity(
            '7.25',
            'business-1',
            PreProcessorMeasurementType.AGENT,
            { source: 'agent' },
            '2023-03-10T00:00:00.000Z',
        );
        await StandardMeasurementPreProcessorEntity.createStandardMeasurement(input, 'pod-1', {
            getLatestPodLabelsByID: jest.fn(async () => [
                { label_paigo_dimension_id: 'dimension-1', label_paigo_customer_id: 'customer-1' },
            ]),
        } as any);
        expect(publish).toHaveBeenCalledWith(
            expect.objectContaining({ customerId: 'customer-1', dimensionId: 'dimension-1', recordValue: 7.25 }),
        );
    });

    it('queries usage through the customer offering and preserves time and interval overrides', async () => {
        const aggregate = jest.fn(async () => [{ dimensionId: 'dimension-1', usage: [] }]);
        const dependencies = serviceDependencies({
            findOne: jest.fn(async () => ({
                data: [{ offering: { offeringId: 'offering-1', dimensions: [{ dimensionId: 'dimension-1' }] } }],
            })),
        });
        const service = new UsageService(
            { getAggregateUsageForDimension: aggregate } as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
        );
        await expect(
            service.findUsageForCustomer(
                { customerId: 'customer-1', businessID: 'business-1' },
                {
                    startTime: '2023-03-01T00:00:00.000Z',
                    endTime: '2023-03-02T00:00:00.000Z',
                    aggregationInterval: 'day',
                } as any,
            ),
        ).resolves.toEqual([{ dimensionId: 'dimension-1', usage: [] }]);
        expect(dependencies.findOne).toHaveBeenCalledWith({ customerId: 'customer-1', businessID: 'business-1' });
        expect(aggregate).toHaveBeenCalledWith(
            expect.objectContaining({
                customerId: 'customer-1',
                clientID: 'customer-1',
                startTime: '2023-03-01T00:00:00.000Z',
                endTime: '2023-03-02T00:00:00.000Z',
                offeringDocument: expect.objectContaining({
                    dimensions: [expect.objectContaining({ dimensionId: 'dimension-1', aggregationInterval: 'day' })],
                }),
            }),
        );
    });

    it('returns customer reads with invoices and the hydrated offering', async () => {
        const influx = {
            getLatestCustomer: jest.fn(async () => [
                {
                    _value: 'Acme',
                    customerId: 'customer-1',
                    paymentChannel: 'manual',
                    offeringId: 'offering-1',
                },
            ]),
            getInvoicesForCustomer: jest.fn(async () => []),
        };
        const dependencies = serviceDependencies({
            findOne: jest.fn(async () => ({ data: [{ offeringId: 'offering-1', dimensions: [] }] })),
        });
        const service = new CustomerService(
            influx as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
        );
        const result = await service.findOne({ customerId: 'customer-1', businessID: 'business-1' });
        expect(result.data[0]).toEqual(
            expect.objectContaining({
                customerId: 'customer-1',
                offeringId: 'offering-1',
                offering: expect.objectContaining({ offeringId: 'offering-1' }),
                invoices: [],
            }),
        );
    });

    it('exposes customer usage and forwards business, customer, and query parameters', async () => {
        const findUsageForCustomer = jest.fn(async () => ({ data: [], message: 'No Customer usage found' }));
        const controller = new PublicAPICustomerController({ findUsageForCustomer } as any);
        const query = { aggregationInterval: 'none' } as any;
        await controller.findUsage('customer-1', { user: { businessID: 'business-1' } } as any, query);
        expect(findUsageForCustomer).toHaveBeenCalledWith(
            { businessID: 'business-1', customerId: 'customer-1' },
            query,
        );
    });

    it('prevents deleting an offering while customers still reference it', async () => {
        const dependencies = serviceDependencies({
            findAllCustomersWithOfferingId: jest.fn(async () => ({ data: [{ customerId: 'customer-1' }] })),
        });
        const service = new OfferingService(
            { getLatestOfferingConfig: jest.fn(async () => [{}]) } as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
        );
        await expect(service.delete({ businessID: 'business-1', offeringId: 'offering-1' })).rejects.toBeInstanceOf(
            ConflictException,
        );
    });

    it('wraps customer usage results without changing their records', async () => {
        const usage = [{ dimensionId: 'dimension-1', usage: [{ value: '3' }] }];
        const dependencies = serviceDependencies({
            findUsageForCustomer: jest.fn(async () => usage),
        });
        const service = new CustomerService(
            {} as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
            dependencies as any,
        );
        await expect(
            service.findUsageForCustomer(
                { customerId: 'customer-1', businessID: 'business-1' },
                { aggregationInterval: 'day' } as any,
            ),
        ).resolves.toEqual({ data: usage, message: 'Found usage' });
    });
});
