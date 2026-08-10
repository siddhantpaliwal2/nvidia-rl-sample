import { NotFoundException } from '@nestjs/common';

import { BillingService } from './billing.service';
import { Billing, billingScheduleConsumers } from './entities/billing.entity';
import { CustomerService } from '../customer/customer.service';
import { schedulerType, SupportedMeasurementFrequencies } from '../scheduler/dto/scheduler.dto';
import { SchedulerService } from '../scheduler/scheduler.service';
import { UsageService } from '../usage/usage.service';

const point = () => ({ tag: jest.fn(), stringField: jest.fn() });

describe('Customer billing schedule migration', () => {
    afterEach(() => jest.restoreAllMocks());

    it('keeps BillingService constructible across the dependency migration', () => {
        expect(new BillingService({} as any, {} as any, {} as any)).toBeDefined();
    });

    const customerService = (scheduler: Record<string, jest.Mock>) => {
        const influx = { getPoint: jest.fn(point), loadPoints: jest.fn() };
        return {
            influx,
            service: new CustomerService(influx as any, scheduler as any, {} as any, {} as any, {} as any),
        };
    };

    it('creates a monthly billing schedule only when a new customer has an offering', async () => {
        const scheduler = { create: jest.fn() };
        const { service } = customerService(scheduler);
        await service.create(
            {
                businessID: 'business-1',
                customerName: 'Acme',
                paymentChannel: 'manual',
                offeringId: 'offering-1',
            } as any,
            'subject-1',
        );
        expect(scheduler.create).toHaveBeenCalledTimes(1);
        expect(scheduler.create).toHaveBeenCalledWith(
            expect.objectContaining({
                schedulerType: schedulerType.billing,
                rate: SupportedMeasurementFrequencies.monthly,
                businessID: 'business-1',
                subject: 'subject-1',
                scheduleParameters: expect.objectContaining({ customerId: expect.any(String) }),
            }),
        );

        scheduler.create.mockClear();
        await service.create(
            { businessID: 'business-1', customerName: 'No plan', paymentChannel: 'manual' } as any,
            'subject-1',
        );
        expect(scheduler.create).not.toHaveBeenCalled();
    });

    it('replaces the billing schedule when an enrolled customer changes offering', async () => {
        const scheduler = { create: jest.fn(), remove: jest.fn() };
        const { service } = customerService(scheduler);
        jest.spyOn(service, 'findOne').mockResolvedValue({
            data: [
                {
                    customerId: 'customer-1',
                    customerName: 'Acme',
                    paymentChannel: 'manual',
                    offeringId: 'offering-old',
                },
            ],
            message: 'Found Customer',
        } as any);
        await service.update(
            { customerId: 'customer-1', businessID: 'business-1', offeringId: 'offering-new' } as any,
            'subject-1',
        );
        expect(scheduler.remove).toHaveBeenCalledWith({
            schedulerID: 'customer-1',
            businessID: 'business-1',
            isBillingQueue: true,
        });
        expect(scheduler.create).toHaveBeenCalledWith(
            expect.objectContaining({
                schedulerID: 'customer-1',
                businessID: 'business-1',
                subject: 'subject-1',
                scheduleParameters: { customerId: 'customer-1', businessID: 'business-1' },
            }),
        );
    });

    it('continues an offering update when the previous billing schedule is already absent', async () => {
        const scheduler = { create: jest.fn(), remove: jest.fn(async () => { throw new NotFoundException(); }) };
        const { service } = customerService(scheduler);
        jest.spyOn(service, 'findOne').mockResolvedValue({
            data: [
                {
                    customerId: 'customer-1',
                    customerName: 'Acme',
                    paymentChannel: 'manual',
                    offeringId: 'offering-old',
                },
            ],
            message: 'Found Customer',
        } as any);
        await expect(
            service.update(
                { customerId: 'customer-1', businessID: 'business-1', offeringId: 'offering-new' } as any,
                'subject-1',
            ),
        ).resolves.toEqual(expect.objectContaining({ customerId: 'customer-1' }));
        expect(scheduler.create).toHaveBeenCalledTimes(1);
    });

    it('builds an invoice from customer usage and records its billed time range', async () => {
        const loadPoints = jest.fn();
        const getPoint = jest.fn(point);
        const generateInvoiceForUsageTotal = jest.fn(async () => ({ invoiceId: 'invoice-1' }));
        const migratedDependencies = {
            findOne: jest.fn(async () => ({ data: [{ offering: { billingCycle: 'monthly' } }] })),
            generateInvoiceForUsageTotal,
        };
        const service = new BillingService(
            { getPoint, loadPoints } as any,
            migratedDependencies as any,
            migratedDependencies as any,
        );
        jest.spyOn(Billing, 'billingCycleToTimeRange').mockReturnValue({
            startTime: '2023-02-01T00:00:00.000Z',
            endTime: '2023-02-28T00:00:00.000Z',
        });
        await service.create({
            data: {
                businessID: 'business-1',
                scheduleParameters: { customerId: 'customer-1' },
            },
        } as any);
        expect(generateInvoiceForUsageTotal).toHaveBeenCalledWith({
            businessID: 'business-1',
            customerId: 'customer-1',
            start: '2023-02-01T00:00:00.000Z',
            end: '2023-02-28T00:00:00.000Z',
        });
        expect(loadPoints).toHaveBeenCalledTimes(1);
        expect(getPoint.mock.results[0].value.tag).toHaveBeenCalledWith('invoiceId', 'invoice-1');
        expect(getPoint.mock.results[0].value.tag).toHaveBeenCalledWith('customerId', 'customer-1');
    });

    it('routes billing scheduler emissions exclusively to the billing queue', async () => {
        const queue = { add: jest.fn() };
        const billingQueue = { add: jest.fn() };
        const service = new SchedulerService(queue as any, billingQueue as any);
        await service.emitOne({
            schedulerId: 'customer-1',
            payload: {
                dimensionType: 'ignored-for-billing',
                schedulerType: schedulerType.billing,
                schedulerStatus: 'live',
                businessID: 'business-1',
                scheduleParameters: { customerId: 'customer-1' },
                rate: SupportedMeasurementFrequencies.monthly,
                subject: 'subject-1',
            },
        } as any);
        expect(billingQueue.add).toHaveBeenCalledWith(
            billingScheduleConsumers.billingReport,
            expect.objectContaining({
                schedulerID: 'customer-1',
                businessID: 'business-1',
                scheduleParameters: { customerId: 'customer-1' },
            }),
        );
        expect(queue.add).not.toHaveBeenCalled();
    });

    it('keeps non-billing scheduler emissions on the data queue', async () => {
        const queue = { add: jest.fn() };
        const billingQueue = { add: jest.fn() };
        const service = new SchedulerService(queue as any, billingQueue as any);
        await service.emitOne({
            schedulerId: 'measurement-1',
            payload: {
                dimensionType: 'ec2',
                schedulerType: schedulerType.measurement,
                schedulerStatus: 'live',
                businessID: 'business-1',
                scheduleParameters: {},
                rate: SupportedMeasurementFrequencies.monthly,
                subject: 'subject-1',
            },
        } as any);
        expect(queue.add).toHaveBeenCalledWith('ec2', expect.objectContaining({ schedulerID: 'measurement-1' }));
        expect(billingQueue.add).not.toHaveBeenCalled();
    });

    it('returns no usage rather than failing when a customer has no offering', async () => {
        const service = new UsageService(
            { getAggregateUsageForDimension: jest.fn() } as any,
            {} as any,
            {} as any,
            { findOne: jest.fn(async () => ({ data: [{ customerId: 'customer-1' }] })) } as any,
            {} as any,
        );
        await expect(
            service.findUsageForCustomer({ customerId: 'customer-1', businessID: 'business-1' }, {} as any),
        ).resolves.toEqual([]);
    });
});
